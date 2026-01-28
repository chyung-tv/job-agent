"""drafting a new workflow architecture for the job search pipeline"""

from pydantic import BaseModel

"""
A Node is a step in the workflow. It takes in a context and returns a context.
"""


class NodeA:
    def __init__(self):
        self.context = self.Context()

    def example1(self) -> str:
        return "Hello, World!"

    def example2(self) -> int:
        return 123

    def example3(self) -> float:
        return 3.14

    def run(self, inputs: Context) -> Context:
        inputs.example1 = "Hello, World!"
        inputs.example2 = 123
        inputs.example3 = 3.14
        return inputs


class NewWorkflow:
    class Context(BaseModel):
        example1: str
        example2: int
        example3: float

    def __init__(self):
        self.context = self.Context()

    def run(self, inputs: Context) -> Context:
        input = nodeA.run(inputs)
        input = nodeB.run(input)
        input = nodeC.run(input)
        return input
