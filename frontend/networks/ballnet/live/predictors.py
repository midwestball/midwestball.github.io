import os
import pickle
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import numpy as np
import torch
import torch.nn.functional as F
from torch.autograd import Variable

# Import local GATv2TCN and AbstractPredictor
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "NBA-GNN-prediction"))
from gatv2tcn import GATv2TCN

from models import AbstractPredictor

log = logging.getLogger(__name__)

# Constants (matches training script)
SEQ_LENGTH = 10
FEATURE_COLS = ["PTS", "AST", "REB", "TO", "STL", "BLK", "PLUS_MINUS",
                "TCHS", "PASS", "DIST", "PACE", "USG_PCT", "TS_PCT"]
PREDICTION_COLS = ["PTS", "AST", "REB", "TO", "STL", "BLK"]
PRED_INDICES = [FEATURE_COLS.index(c) for c in PREDICTION_COLS]

class LiveGATv2Predictor(AbstractPredictor):
    """
    Live predictor utilizing the trained GATv2TCN model.
    Builds the 10-day historical window dynamically from the pre-processed outputs/data.
    Uses MC Dropout and Conformal Calibration for confidence intervals.
    """
    
    def __init__(self, data_dir: str, model_dir: str, tracking_dir: str, device: str = 'cpu'):
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.tracking_dir = Path(tracking_dir)
        self.device = torch.device(device)
        self.setup_complete = False
        
    def setup(self):
        log.info("Loading LiveGATv2Predictor artefacts...")
        
        # 1. Load data mappings & history
        with open(self.data_dir / 'player_ids.pkl', 'rb') as f:
            self.player_ids = pickle.load(f)
        with open(self.data_dir / 'game_dates.pkl', 'rb') as f:
            self.game_dates = pickle.load(f)
            
        # Load normalized historical features and graphs
        with open(self.data_dir / 'X_seq.pkl', 'rb') as f:
            self.X_seq = pickle.load(f)
        with open(self.data_dir / 'G_seq.pkl', 'rb') as f:
            self.G_seq = pickle.load(f)
            
        def graphs_to_edges(G_seq, player_ids):
            nd = {pid: i for i, pid in enumerate(player_ids)}
            out = []
            for G in G_seq:
                edges = list(G.edges())
                if not edges:
                    n = len(player_ids)
                    out.append(torch.stack([torch.arange(n), torch.arange(n)]).long().to(self.device))
                else:
                    s, d = zip(*edges)
                    s = [nd.get(x, 0) for x in s]; d = [nd.get(x, 0) for x in d]
                    out.append(torch.stack([
                        torch.LongTensor(s + d), torch.LongTensor(d + s)]).to(self.device))
            return out
            
        self.G_edges = graphs_to_edges(self.G_seq, self.player_ids)
            
        # Load temporal team and position arrays
        with open(self.data_dir / 'team_temporal.pkl', 'rb') as f:
            self.team_temporal = pickle.load(f)
        with open(self.data_dir / 'pos_temporal.pkl', 'rb') as f:
            self.pos_temporal = pickle.load(f)
            
        with open(self.data_dir / 'n_teams.pkl', 'rb') as f:
            self.n_teams = pickle.load(f)
            
        # Load normalization parameters (locked post-2023)
        self.mu_per_day = np.load(self.data_dir / 'mu_per_day.npy')
        self.sd_per_day = np.load(self.data_dir / 'sd_per_day.npy')
        
        # Load conformal residuals
        with open(self.tracking_dir / 'conformal_residuals.pkl', 'rb') as f:
            self.val_residuals = pickle.load(f)
            
        self.N = len(self.player_ids)
        self.pid_to_idx = {pid: i for i, pid in enumerate(self.player_ids)}
        
        # 3. Load Model weights
        team_emb_in = 2
        pos_emb_in = 2
        model_in = len(FEATURE_COLS) + team_emb_in + pos_emb_in
        
        self.team_embedding = torch.nn.Linear(self.n_teams, team_emb_in).to(self.device)
        self.n_positions = 3 # Fixed in ballnet
        self.position_embedding = torch.nn.Linear(self.n_positions, pos_emb_in).to(self.device)
        
        self.model = GATv2TCN(
            in_channels=model_in,
            out_channels=6,
            len_input=SEQ_LENGTH,
            len_output=1,
            temporal_filter=64,
            out_gatv2conv=32,
            dropout_tcn=0.25,
            dropout_gatv2conv=0.5,
            head_gatv2conv=4
        ).to(self.device)
        
        # Ensure we are loading on correct device
        self.model.load_state_dict(torch.load(self.model_dir / 'model.pth', map_location=self.device))
        self.team_embedding.load_state_dict(torch.load(self.model_dir / 'team_emb.pth', map_location=self.device))
        self.position_embedding.load_state_dict(torch.load(self.model_dir / 'pos_emb.pth', map_location=self.device))
        
        self.setup_complete = True
        log.info("✓ LiveGATv2Predictor loaded successfully.")

    def _get_latest_day_index(self) -> int:
        """Helper to get the most recent data index"""
        return len(self.game_dates) - 1
        
    def _build_input_tensor(self, pid: int, day_idx: int) -> tuple[torch.Tensor, list]:
        """Builds the (1, N, F, T) tensor for a specific day using the 10-day lookback"""
        if day_idx < SEQ_LENGTH - 1:
            raise ValueError(f"Not enough historical data before day index {day_idx}")

        # The inference code needs ALL players for the GCN, we mask out the specific player later.
        input_days = list(range(day_idx - SEQ_LENGTH + 1, day_idx + 1))
        
        with torch.no_grad():
            team_t = torch.FloatTensor(self.team_temporal[day_idx]).to(self.device)
            pos_t = torch.FloatTensor(self.pos_temporal[day_idx]).to(self.device)
            tv = self.team_embedding(team_t)
            pv = self.position_embedding(pos_t)
            
            Xl = []
            for abs_day in input_days:
                # X_seq is normalized and forward-filled by 01_data_pipeline and Phase 3
                x_t = torch.cat([torch.FloatTensor(self.X_seq[abs_day]).to(self.device), tv, pv], dim=1)
                Xl.append(x_t)
                
            x_input = torch.stack(Xl, dim=-1)[None, ...] # Shape: (1, N, 17, 10)
            g_window = self.G_edges[day_idx - SEQ_LENGTH + 1 : day_idx + 1]
            
        return x_input, g_window

    def predict_point_estimate(self, player_id: int, stat: str, date: str = None) -> float:
        """
        Returns a single point estimate using model.eval().
        Note: The predictor expects date to match today. It strictly uses historical `outputs/data/`
        updated earlier today.
        """
        if not self.setup_complete:
            self.setup()
            
        pidx = self.pid_to_idx.get(player_id)
        if pidx is None:
            return 0.0
            
        if stat not in PREDICTION_COLS:
            return 0.0
        si = PREDICTION_COLS.index(stat)
        
        latest_idx = self._get_latest_day_index()
        x_input, g_window = self._build_input_tensor(pidx, latest_idx)
        
        self.model.eval()
        self.team_embedding.eval()
        self.position_embedding.eval()
        
        with torch.no_grad():
            preds_z = self.model(x_input, g_window)[0].cpu().numpy()
            
        # Un-normalize
        mu_d = self.mu_per_day[latest_idx, 0, PRED_INDICES]
        sd_d = self.sd_per_day[latest_idx, 0, PRED_INDICES]
        preds_raw = preds_z * sd_d + mu_d
        
        return float(preds_raw[pidx, si])

    def predict_conformal_probability(self, player_id: int, stat: str, threshold: float, date: str = None) -> Dict[str, float]:
        """
        Uses MC Dropout (20 samples) combined with empirical residuals from validation
        to construct a full distribution, returning the probability of going OVER the threshold.
        """
        if not self.setup_complete:
            self.setup()
            
        pidx = self.pid_to_idx.get(player_id)
        if pidx is None:
            return {"p_over": 0.0, "p_under": 0.0}
            
        if stat not in PREDICTION_COLS:
            return {"p_over": 0.0, "p_under": 0.0}
            
        si = PREDICTION_COLS.index(stat)
        latest_idx = self._get_latest_day_index()
        x_input, g_window = self._build_input_tensor(pidx, latest_idx)
        
        mu_d = self.mu_per_day[latest_idx, 0, PRED_INDICES]
        sd_d = self.sd_per_day[latest_idx, 0, PRED_INDICES]
        
        # MC Dropout
        self.model.train() # Enable dropout!
        self.team_embedding.train()
        self.position_embedding.train()
        
        n_samples = 20
        samples_raw = []
        with torch.no_grad():
            for _ in range(n_samples):
                pred_z = self.model(x_input, g_window)[0].cpu().numpy()
                pred_raw = pred_z * sd_d + mu_d
                samples_raw.append(pred_raw[pidx, si])
                
        # Combine with conformal residuals structure
        # Add random validation residuals to MCMC samples representing base uncertainty
        valid_residuals = self.val_residuals.get(stat, [])
        if len(valid_residuals) == 0:
            return {"p_over": 0.0, "p_under": 0.0}
            
        # Draw 100 random residuals for each of the 20 MCMC samples = 2000 empirical samples
        samples_raw = np.array(samples_raw)
        res_sample = np.random.choice(valid_residuals, size=(n_samples, 100))
        dist = (samples_raw[:, None] + res_sample).flatten()
        
        p_over = float(np.mean(dist > threshold))
        p_under = 1.0 - p_over
        
        return {"p_over": p_over, "p_under": p_under}
