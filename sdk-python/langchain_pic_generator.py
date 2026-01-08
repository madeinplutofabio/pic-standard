from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List

# Define the PIC Schema for the LLM
class PICContract(BaseModel):
    intent: str = Field(description="The reason for the action")
    impact: str = Field(description="read, write, money, or irreversible")
    provenance_ids: List[str] = Field(description="IDs of sources used")
    evidence_claims: List[str] = Field(description="Justification for the action")
    tool_name: str
    tool_args: dict

# Initialize LLM with Structured Output
llm = ChatOpenAI(model="gpt-4o")
structured_llm = llm.with_structured_output(PICContract)

# Example Usage
prompt = "The CFO approved the AWS invoice in the PDF 'auth_01'. Pay $500 now."
pic_proposal = structured_llm.invoke(prompt)

print(f"Contract Generated: {pic_proposal.intent} | Impact: {pic_proposal.impact}")
# Now pass 'pic_proposal' to the PIC Verifier before executing the tool!
