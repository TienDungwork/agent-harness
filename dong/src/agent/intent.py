from src.llm import invoke_text

INTENT_PROMPT = """Phân loại câu hỏi của người dùng vào 1 trong 5 loại sau:
- query_data: hỏi về số liệu, đếm số lượng, liệt kê biển số, sự kiện (vd: có bao nhiêu xe, cho xem biển số).
- how_to: hỏi về cách sử dụng, cách làm một việc gì đó trên hệ thống VMS/camera (vd: làm sao để thêm camera, cách xem lại video).
- troubleshoot: hỏi cách xử lý sự cố, lỗi (vd: tại sao camera mất kết nối).
- concept: hỏi về khái niệm (vd: AIOC là gì, hàng rào ảo là gì).
- out_of_scope: các câu hỏi khác không liên quan đến hệ thống VMS, giao thông, an ninh (vd: thời tiết hôm nay thế nào).

Chỉ trả về ĐÚNG 1 từ khóa (query_data, how_to, troubleshoot, concept, out_of_scope), KHÔNG giải thích.
"""

def classify_intent(question: str) -> str:
    from src.llm import use_offline_tools
    if use_offline_tools():
        return "query_data"
        
    ans = invoke_text(INTENT_PROMPT, f"Câu hỏi: {question}").strip().lower()
    for valid in ["query_data", "how_to", "troubleshoot", "concept", "out_of_scope"]:
        if valid in ans:
            return valid
    return "query_data"  # fallback
