import os
from google import genai
from database import Database

class BaseAgent:
    def __init__(self, name: str, system_prompt: str, db: Database):
        self.name = name
        self.system_prompt = system_prompt
        self.db = db

    def _call_llm(self, user_prompt: str) -> str:
        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            print(f"[{self.name}] GEMINI_API_KEY not set. Running in SIMULATION mode.")
            # Return mock responses depending on the calling agent's name/intent
            if self.name == "Extractor":
                return (
                    "1. Quantum Supremacy: Achieving computational advantage over classical supercomputers.\n"
                    "2. Topological Qubits: Development of fault-tolerant hardware architectures.\n"
                    "3. Hybrid Quantum-Classical Algorithms: NISQ-era optimization methods."
                )
            elif self.name == "Risk Analyst":
                return (
                    "1. Extreme error susceptibility and high decoherence rates.\n"
                    "2. Complex materials engineering and low braid reliability.\n"
                    "3. High latency in classical-quantum communication loop."
                )
            else:
                return (
                    "# Executive Summary: Quantum Computing Readiness (OOP)\n\n"
                    "## Key Findings\n"
                    "Quantum computing is transitioning from purely theoretical physics to early-stage engineering, "
                    "primarily driven by NISQ optimization and topological fault-tolerance exploration.\n\n"
                    "## Risks & Readiness Verdict\n"
                    "1. **Decoherence**: High sensitivity to noise requires massive error-correction scaling.\n"
                    "2. **Materials Pipeline**: Topological systems are conceptually sound but lack stable hardware.\n"
                    "3. **Algorithms**: Hybrid solvers offer near-term value but face overhead bottlenecks.\n\n"
                    "**Verdict**: Technology Readiness Level (TRL) is 4 (Component validation in laboratory environment)."
                )
                
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=user_prompt,
            config={"system_instruction": self.system_prompt},
        )
        return response.text

    def run(self, input_data: str) -> str:
        print(f"[{self.name}] Running task...")
        output_data = self._call_llm(input_data)
        self.db.log_run(self.name, input_data, output_data)
        print(f"[{self.name}] Run logged to database.")
        return output_data

class ExtractorAgent(BaseAgent):
    def __init__(self, db: Database):
        system_prompt = (
            "You are an expert research agent. Given a technical query, identify the top 3 "
            "core advancements or breakthrough developments in this field. Output them as a numbered list."
        )
        super().__init__(name="Extractor", system_prompt=system_prompt, db=db)

class RiskAnalystAgent(BaseAgent):
    def __init__(self, db: Database):
        system_prompt = (
            "You are a technical risk analyst. Given a list of advancements in a technology field, "
            "identify key engineering risks, bottlenecks, or challenges associated with each advancement. "
            "Respond with a corresponding numbered list matching the advancements."
        )
        super().__init__(name="Risk Analyst", system_prompt=system_prompt, db=db)

class SynthesizerAgent(BaseAgent):
    def __init__(self, db: Database):
        system_prompt = (
            "You are a principal technical editor. Synthesize the given advancements and risks "
            "into a structured executive summary report in Markdown. Highlight key findings, recommendations, "
            "and a final technical readiness verdict."
        )
        super().__init__(name="Synthesizer", system_prompt=system_prompt, db=db)
