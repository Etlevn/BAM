from edsl import Model, QuestionFreeText, Survey
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Create model instance (e.g., GPT-4o)
model = Model("gpt-4o")

# Create free text question
question = QuestionFreeText(
    question_name="relativity",
    question_text="Can you summarize the theory of relativity in 2 sentences?"
)

# Create survey and add question
survey = Survey(questions=[question])

# Run survey and get results
results = survey.by(model).run()

# Print model response
print("Response：", results[0].answer)