import subprocess
import time
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s  [MASTER]  %(message)s")
log = logging.getLogger(__name__)

# Update this path to point to the nested script
PIPELINE_SCRIPT = "networks/reproduction/01_data_pipeline.py"
KAMIKAZE_CODE = 42

def run_scraper():
    while True:
        log.info(f"Spawning new process for {PIPELINE_SCRIPT}...")
        
        # Run the target script and wait for it to finish
        process = subprocess.run([sys.executable, PIPELINE_SCRIPT])
        
        if process.returncode == KAMIKAZE_CODE:
            log.info("Process performed a controlled exit. Restarting immediately...")
            # Optional: Add a tiny sleep just to be safe, e.g., time.sleep(2)
            time.sleep(2)
            continue
        elif process.returncode == 0:
            log.info("Process finished successfully (all data gathered). Exiting master script.")
            break
        else:
            log.error(f"Process crashed with unexpected return code: {process.returncode}. Halting.")
            break

if __name__ == "__main__":
    run_scraper()