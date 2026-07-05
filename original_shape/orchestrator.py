import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env next to this file, not from the caller's cwd.
load_dotenv(Path(__file__).parent / ".env")

from database import Database
from agents import ExtractorAgent, RiskAnalystAgent, SynthesizerAgent

def run_system(query: str):
    print("=== Starting OOP Agent System ===")
    
    # 1. Database initialization
    db = Database()
    try:
        db.init_db()
    except Exception as e:
        print(f"Database init warning/error: {e}")
        
    # 2. Instantiate agents
    extractor = ExtractorAgent(db)
    risk_analyst = RiskAnalystAgent(db)
    synthesizer = SynthesizerAgent(db)
    
    # 3. Pipeline execution
    # Agent 1 extracts advancements
    advancements = extractor.run(query)
    print(f"\n--- Extractor Output ---\n{advancements}\n")
    
    # Agent 2 analyzes risks (receives field description and advancements output)
    risks_input = f"Field: {query}\nAdvancements:\n{advancements}"
    risks = risk_analyst.run(risks_input)
    print(f"\n--- Risk Analyst Output ---\n{risks}\n")
    
    # Agent 3 synthesizes final report
    synthesis_input = f"Topic: {query}\nAdvancements:\n{advancements}\n\nRisks & Bottlenecks:\n{risks}"
    report = synthesizer.run(synthesis_input)
    print(f"\n--- Synthesized Executive Report ---\n{report}\n")
    
    print("=== OOP Agent System Execution Complete ===")

if __name__ == "__main__":
    test_query = "Quantum Computing"
    if len(sys.argv) > 1:
        test_query = sys.argv[1]
    run_system(test_query)
