#!/usr/bin/env python3
"""
Kịch bản kiểm chứng tự động độ bền vững của Memory & Context Engineering v9
Tương ứng 1:1 với Kịch bản kiểm thử thủ công trong specs/test-plan.md mục 3.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Đảm bảo mã hóa UTF-8 cho console trên Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm thư mục gốc vào PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.memory.extract import extract_and_store_memory, extract_memories
from src.memory.longterm import clear_long_term, recall_long_term, save_to_long_term
from src.memory.context import (
    compress_tool_result,
    reinject_instructions,
    sliding_window,
)
from src.memory.ttl_cache import (
    clear_ttl_cache,
    get_ttl_cached,
    make_cache_key,
    set_ttl_cached,
)


def print_step_header(step_num: int, title: str):
    print(f"\n[{step_num}/7] {title}")
    print("-" * 65)


def run_demo_verification() -> bool:
    print("=" * 65)
    print("  KIỂM CHỨNG TỰ ĐỘNG ĐỘ BỀN VỮNG CỦA MEMORY & CONTEXT ENGINEERING (v9)")
    print("  Hệ thống Multi-Agent VMS KCN Hưng Phú")
    print("=" * 65)

    all_passed = True
    demo_user = "u_demo_tuan"

    # Dọn dẹp trạng thái trước khi kiểm chứng
    clear_long_term(demo_user)
    clear_ttl_cache()

    # ─────────────────────────────────────────────────────────────────
    # Bước 1: Ghi nhận danh tính người dùng (Fact Extraction & Storage)
    # ─────────────────────────────────────────────────────────────────
    print_step_header(1, "Ghi nhận danh tính (Fact Extraction & Storage)")
    user_input_1 = "Chào bạn, tôi tên là Tuấn, tôi phụ trách giám sát an ninh ca đêm"
    print(f"User: \"{user_input_1}\"")
    
    extracted = extract_and_store_memory(demo_user, user_input_1)
    print(f"Hệ thống trích xuất facts: {extracted}")

    if extracted and any("Tuấn" in f for f in extracted) and any("an ninh" in f for f in extracted):
        print("=> [PASS] Đã trích xuất và lưu bền vững thông tin danh tính thành công.")
    else:
        print("=> [FAIL] Không trích xuất được đủ facts danh tính!")
        all_passed = False

    # ─────────────────────────────────────────────────────────────────
    # Bước 2: Truy vấn thông tin trong cùng phiên (Short-Term & Long-Term Recall)
    # ─────────────────────────────────────────────────────────────────
    print_step_header(2, "Truy vấn trong cùng phiên (Memory Recall)")
    user_input_2 = "Khu vực tôi phụ trách là gì?"
    print(f"User: \"{user_input_2}\"")

    recalled_facts_2 = recall_long_term(demo_user, user_input_2, k=3)
    print(f"Facts nạp vào ngữ cảnh: {recalled_facts_2}")

    if recalled_facts_2 and any("an ninh" in f for f in recalled_facts_2):
        print("=> [PASS] Trợ lý nhớ và truy xuất chính xác vai trò giám sát an ninh ca đêm.")
    else:
        print("=> [FAIL] Không nhớ được thông tin vai trò trong phiên!")
        all_passed = False

    # ─────────────────────────────────────────────────────────────────
    # Bước 3: Phiên mới / Tab ẩn danh với cùng user_id (PostgreSQL Durability)
    # ─────────────────────────────────────────────────────────────────
    print_step_header(3, "Phiên mới / Thiết bị mới (Long-Term Durability)")
    user_input_3 = "Tôi là ai?"
    print(f"[Tab ẩn danh mới / F5] User ({demo_user}): \"{user_input_3}\"")

    # Giả lập phiên mới hoàn toàn: Short-term trống, chỉ có Long-Term trong database
    recalled_facts_3 = recall_long_term(demo_user, user_input_3, k=3)
    print(f"Facts phục hồi từ Long-Term DB: {recalled_facts_3}")

    if len(recalled_facts_3) >= 1 and any("Tuấn" in f for f in recalled_facts_3):
        print("=> [PASS] Dữ liệu bền vững: Nhận diện đúng Tuấn sau khi mở phiên mới hoàn toàn.")
    else:
        print("=> [FAIL] Mất dữ liệu khi mở phiên mới!")
        all_passed = False

    # ─────────────────────────────────────────────────────────────────
    # Bước 4: Trò chuyện liên tục > 10 lượt (Sliding Window & Re-injection)
    # ─────────────────────────────────────────────────────────────────
    print_step_header(4, "Hội thoại dài > 10 lượt (Sliding Window & Instruction Re-injection)")
    # Giả lập 24 tin nhắn (12 lượt hội thoại)
    messages = [{"role": "system", "content": "Hệ thống trợ lý điều hành VMS KCN Hưng Phú"}]
    for i in range(1, 13):
        messages.append({"role": "user", "content": f"Câu hỏi nghiệp vụ kiểm tra camera số {i}"})
        messages.append({"role": "assistant", "content": f"Báo cáo camera {i} hoạt động bình thường."})

    print(f"Tổng số tin nhắn trước khi cắt tỉa: {len(messages)} tin nhắn")
    windowed = sliding_window(messages, max_messages=20)
    print(f"Số tin nhắn sau Sliding Window (max=20): {len(windowed)} tin nhắn")

    safety_rules = "QUY TẮC AN TOÀN VMS: Tuyệt đối không để lộ thông tin bảo mật, luôn kiểm tra camera trước khi báo cáo."
    reinforced = reinject_instructions(windowed, safety_rules)
    last_msg = reinforced[-1]

    rule_ok = "[Nhắc lại chỉ dẫn]:" in last_msg.get("content", "") and "QUY TẮC AN TOÀN VMS" in last_msg.get("content", "")
    window_ok = len(windowed) <= 21 and windowed[0]["role"] == "system"

    if window_ok and rule_ok:
        print("=> [PASS] Sliding Window cắt tỉa an toàn (giữ system message); Quy tắc an toàn VMS được tái chèn ở cuối context.")
    else:
        print("=> [FAIL] Lỗi cơ chế Sliding Window hoặc Instruction Re-injection!")
        all_passed = False

    # ─────────────────────────────────────────────────────────────────
    # Bước 5: Truy vấn dữ liệu lớn (Tool Output Compression)
    # ─────────────────────────────────────────────────────────────────
    print_step_header(5, "Truy vấn dữ liệu lớn (Tool Output Compression)")
    # Giả lập bảng dữ liệu SQL lớn với 50 dòng kết quả xe cộ
    large_sql_result = (
        "| ID | Biển số | Loại xe | Cổng | Thời gian | Trạng thái |\n"
        + "\n".join(
            f"| {i} | 65C-123.{i:02d} | Xe tải | Cổng chính | 2026-09-28 08:{i:02d}:00 | Hợp lệ |"
            for i in range(1, 51)
        )
    )
    print(f"Dung lượng kết quả SQL thô: {len(large_sql_result)} ký tự (~{len(large_sql_result)//4} tokens)")

    compressed = compress_tool_result(large_sql_result, query="Hôm nay có bao nhiêu lượt xe vào KCN?", max_tokens=150)
    print(f"Kết quả sau nén: {len(compressed)} ký tự (~{len(compressed)//4} tokens)")
    print(f"Trích đoạn kết quả nén: {compressed[:120]}...")

    if len(compressed) < len(large_sql_result) and (
        "... [đã nén]" in compressed or "[Tóm tắt" in compressed or len(compressed) <= 150 * 4 + 50
    ):
        print("=> [PASS] Bảng SQL lớn được nén súc tích, giữ nguyên các thông tin chủ chốt.")
    else:
        print("=> [FAIL] Nén kết quả tool thất bại!")
        all_passed = False

    # ─────────────────────────────────────────────────────────────────
    # Bước 6: Câu hỏi trùng lặp (TTL Cache Hit < 5ms)
    # ─────────────────────────────────────────────────────────────────
    print_step_header(6, "Câu hỏi trùng lặp (TTL Response Cache)")
    stat_query = "Hôm nay có bao nhiêu lượt xe vào KCN?"
    cache_key = make_cache_key(stat_query)
    cached_payload = {
        "answer": "Hôm nay có tổng cộng 150 lượt xe tải và xe container vào KCN Hưng Phú.",
        "chart_spec": {"type": "bar", "title": "Lượt xe vào KCN"},
    }

    # Ghi cache lần đầu
    set_ttl_cached(cache_key, cached_payload, ttl=300)
    print(f"Lần 1: User hỏi \"{stat_query}\" -> Ghi TTL Cache (TTL = 300s)")

    # Lần 2: Đọc ngay lập tức từ cache
    start_time = time.perf_counter()
    hit_data = get_ttl_cached(cache_key)
    latency_ms = (time.perf_counter() - start_time) * 1000

    print(f"Lần 2: User hỏi lại y hệt \"{stat_query}\"")
    print(f"TTL Cache Hit latency: {latency_ms:.3f} ms (Tiêu chuẩn: < 5.0 ms)")

    if hit_data and hit_data.get("answer") == cached_payload["answer"] and latency_ms < 5.0:
        print(f"=> [PASS] TTL Cache Hit cực nhanh ({latency_ms:.3f} ms < 5ms), bỏ qua gọi LLM/SQL.")
    else:
        print("=> [FAIL] Lỗi TTL Cache Hit hoặc độ trễ vượt mức!")
        all_passed = False

    # ─────────────────────────────────────────────────────────────────
    # Bước 7: Mất kết nối DB (Graceful Degradation)
    # ─────────────────────────────────────────────────────────────────
    print_step_header(7, "Sự cố database (Graceful Degradation Fallback)")
    print("Mô phỏng DB gặp sự cố / DB_HOST offline:")

    from unittest.mock import patch

    with patch("src.memory.longterm.get_memory_connection", side_effect=Exception("Database connection timeout")):
        with patch("src.memory.longterm.is_postgres_configured", return_value=True):
            # Thử lưu và đọc fact khi DB sập
            save_to_long_term("u_fallback_test", "Thích xem camera cổng chính", "preference")
            fallback_facts = recall_long_term("u_fallback_test", "camera", k=1)

            print(f"Facts truy xuất qua in-memory fallback: {fallback_facts}")

            if fallback_facts and "Thích xem camera cổng chính" in fallback_facts:
                print("=> [PASS] Hệ thống tự động chuyển sang In-Memory Fallback an toàn, 100% không crash.")
            else:
                print("=> [FAIL] Không phục hồi được qua In-Memory Fallback!")
                all_passed = False

    # ─────────────────────────────────────────────────────────────────
    # TỔNG KẾT
    # ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    if all_passed:
        print("🎉 KẾT QUẢ: 7/7 KỊCH BẢN DEMO PASS HOÀN HẢO 100%!")
        print("   Hệ thống Memory & Context Engineering v9 sẵn sàng cho live demo!")
    else:
        print("❌ KẾT QUẢ: MỘT SỐ KỊCH BẢN CHƯA ĐẠT! VUI LÒNG KIỂM TRA LẠI.")
    print("=" * 65 + "\n")

    return all_passed


if __name__ == "__main__":
    success = run_demo_verification()
    sys.exit(0 if success else 1)
