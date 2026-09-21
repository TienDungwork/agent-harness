import os
import re
from pathlib import Path
from src.llm import invoke_text

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "vms"

def retrieve_docs(question: str) -> str:
    # MVP Keyword retrieve, no vector DB
    keywords = set(re.findall(r'\w+', question.lower()))
    best_match = ""
    max_score = 0
    
    if not DOCS_DIR.exists():
        return ""
        
    for file_path in DOCS_DIR.glob("*.md"):
        try:
            content = file_path.read_text(encoding="utf-8")
            score = sum(1 for kw in keywords if kw in content.lower())
            if score > max_score:
                max_score = score
                best_match = content
        except Exception:
            pass
            
    if max_score == 0:
        return ""
        
    # Lấy 2000 ký tự đầu tiên để tránh context quá dài
    return best_match[:2000]

DOC_PROMPT = """Bạn là trợ lý hệ thống VMS.
Người dùng hỏi: {question}

Tài liệu tham khảo:
{docs}

Yêu cầu:
- Trả lời CHỈ dựa vào tài liệu tham khảo.
- Nếu tài liệu không có thông tin, trả lời "Không có trong tài liệu".
- Nếu người dùng yêu cầu vẽ sơ đồ, hãy thêm markdown hoặc mermaid các bước từ tài liệu.
"""

def handle_docs_intent(question: str) -> str:
    docs = retrieve_docs(question)
    if not docs:
        return "Không có trong tài liệu"
    
    prompt = DOC_PROMPT.format(question=question, docs=docs)
    ans = invoke_text(prompt, question)
    return ans
