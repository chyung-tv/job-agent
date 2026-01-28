"""drafting a new workflow architecture for the job search pipeline"""

from http import HTTPStatus
from pydantic import BaseModel

"""
A Node is a step in the workflow. It takes in a context and returns a context.
"""

"""In the context of our application, Matcher is a node"""


class NodeA:
    def __init__(self):
        self.context = self.Context()

    def example1(self) -> str:
        return "Hello, World!"

    def example2(self) -> int:
        return 123

    def example3(self) -> float:
        return 3.14

    def db_persist(self, data_to_save: DataModel) -> None:
        """
        Persist data to the database. In our current setup up it seems that every step has its own data persistent in respective tables. We should consider if we want to consolidate the data into a single table, but I'm not sure whether we should do it or how should we do it efficiently.
        """
        pass

    def run(self, inputs: Context) -> Context:
        inputs.example1 = "Hello, World!"
        inputs.example2 = 123
        inputs.example3 = 3.14
        return inputs


"""
A Workflow is a collection of nodes. It takes in a context and returns a context.
"""


class NewWorkflow:
    """Context should work as a state manager across the same workflow. Different workflow might have different workflow context. Heavy data are pulled from the database according to the run ID or necessary unit identifiers. not sure if we should put the context class inside the workflow class or do it separately"""

    class Context(BaseModel):
        run_id: str
        job_query: str
        user_profile: UserProfile

    def __init__(self):
        self.context = self.Context()

    def run(self, inputs: Context) -> Context:
        input = nodeA.run(inputs)
        input = nodeB.run(input)
        input = nodeC.run(input)
        return input


"""
I think such architecture is very convenient to set a fast API endpoint such that in that endpoint I can just simply trigger the workflow using the context object and it's easier for me to think about input parameter for the API endpoint and the output should be the context object?
"""

from fastapi import FastAPI
from typing import Optional

app = FastAPI()


@app.post("/workflow/NewWorkflow")
def run_workflow(context: NewWorkflow.Context):
    workflow = NewWorkflow()
    result = workflow.run(context)
    return HTTPStatus.ACCEPTED, result
