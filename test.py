from edsl import Model, QuestionFreeText, Survey
from dotenv import load_dotenv
import os

# 加载 .env 文件中的环境变量
load_dotenv()

# 创建模型实例（如 GPT-4o）
model = Model("gpt-4o")

# 创建自由文本问题
question = QuestionFreeText(
    question_name="relativity",
    question_text="Can you summarize the theory of relativity in 2 sentences?"
)

# 创建调查并添加问题
survey = Survey(questions=[question])

# 运行调查并获取结果
results = survey.by(model).run()

# 打印模型的回复
print("模型回复：", results[0].answer)