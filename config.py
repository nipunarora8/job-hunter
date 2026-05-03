import os
from dotenv import load_dotenv
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "openrouter/auto"  # uses free models automatically

SEARCH_KEYWORDS = [
    "AI Engineer",
    "Machine Learning Engineer",
    "Software Engineer",
    "Computer Vision Engineer",
    "Robotics Software Engineer",
    "Agentic AI Engineer",
    "Perception Engineer",
]

PROFILE_SUMMARY = """
AI Engineer, 3.5 years at Max Planck Institute Berlin. M.Sc. Artificial Intelligence, FAU Erlangen-Nürnberg (GPA 1.7). Published EPJ Data Science, Springer Nature 2026.
AI & Deep Learning: PyTorch, Computer Vision, LLMs, Foundation Models (VLM/VLA), LoRA fine-tuning, YOLOv8, SAM, multi-node multi-GPU distributed training on HPC.
Agentic AI: LangGraph, LangChain, multi-agent pipelines, RAG (ChromaDB), MCP, LLM tool calling, prompt engineering, Claude Code.
Edge AI & Robotics: ROS2, NVIDIA DeepStream, GStreamer, ONNX, Jetson Xavier/Nano, Raspberry Pi, Arduino, Embodied AI, Autonomous Systems.
Software Engineering: Python, C++, Docker, Git, CI/CD, FastAPI, HPC, MongoDB, AWS S3.
English C1, German beginner — needs English-friendly roles only. Open to all locations in Germany and remote.
""".strip()

MIN_RELEVANCE_SCORE = 4  # jobs below this score are discarded entirely
DB_PATH = "jobs.db"
