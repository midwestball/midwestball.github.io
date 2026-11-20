import type { Metadata } from "next";
import { TradeRecommenderClient } from "./TradeRecommenderClient";

export const metadata: Metadata = {
  title: "Trade recommender lab · midwestball",
  description: "Experimental ROS trade recommendations from a linked Sleeper or ESPN league.",
};

export default function TradeRecommenderLabPage() {
  return <TradeRecommenderClient />;
}
