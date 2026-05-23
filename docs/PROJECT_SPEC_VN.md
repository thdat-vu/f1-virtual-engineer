# F1 Virtual Engineer: Tài liệu Đặc tả Dự án (Agent-Ready)

## Tổng quan
**F1 Virtual Engineer** là một hệ thống Agentic AI được thiết kế để đóng vai trò là Kỹ sư Đua xe Ảo (Virtual F1 Race Engineer). Hệ thống xử lý dữ liệu viễn thám (telemetry) thời gian thực, dữ liệu lịch sử và điều kiện đường đua để đưa ra các phân tích chiến thuật (ví dụ: thời điểm vào pit, độ mòn lốp, dự đoán undercut/overcut).

## Kiến trúc: Cấu trúc Monorepo
Dự án được cấu trúc để tách biệt phần tư duy AI (Backend) và phần hiển thị giao diện (Frontend).

### `/backend` (FastAPI + LangGraph)
- **`app/`**: Các API endpoint và cấu hình router.
- **`agents/`**: Logic cốt lõi của Agent sử dụng LangGraph (Nodes, Edges, State).
- **`core/`**: System prompts, các chính sách điều hành và cấu hình LLM.
- **`tools/`**: Các wrapper cho FastF1 API với Pydantic schema để kiểm tra dữ liệu.
- **`rag/`**: Cơ sở dữ liệu Vector (Supabase/ChromaDB) lưu trữ luật lệ FIA và dữ liệu chiến thuật lịch sử.
- **`data/`**: Thư mục cache cục bộ cho dữ liệu telemetry từ FastF1.
- **`eval/`**: Bộ công cụ đánh giá và "Golden Sets" để kiểm tra hiệu suất của Agent.

### `/frontend` (Next.js 15 + TypeScript)
- **Dashboard**: Giao diện hiệu suất cao sử dụng Tailwind CSS để hiển thị dữ liệu telemetry và phản hồi của Agent theo thời gian thực.

## Tech Stack
- **Ngôn ngữ**: Python 3.11+ (Backend), TypeScript (Frontend).
- **Điều phối Agent**: LangGraph, LangChain.
- **Trí tuệ nhân tạo**: Gemini API (Flash/Pro) để phân tích dữ liệu và lập luận.
- **Nguồn dữ liệu**: FastF1 (Dữ liệu telemetry trực tiếp và lịch sử).
- **Cơ sở dữ liệu**: Supabase (PostgreSQL + Vector).
- **Giao diện**: Tailwind CSS (Phong cách đua xe chuyên nghiệp).

## Năng lực cốt lõi của Agent (Hướng dẫn cho Agent-to-Agent)
1. **Phân tích Telemetry**: Truy xuất và so sánh tốc độ, cấp số, chân ga, và phanh giữa các vòng đua/tay đua.
2. **Dự đoán chiến thuật**: Dự báo "Lap Time Decay" (sự sụt giảm thời gian vòng chạy) và đề xuất thời điểm vào pit tối ưu.
3. **Diễn giải Radio**: Phân tích các đoạn hội thoại radio để phát hiện lỗi kỹ thuật (sử dụng lập luận LLM).
4. **Mô phỏng chiến lược**: Sử dụng dữ liệu lịch sử để mô phỏng các kịch bản undercut/overcut.

## Thiết lập & Khởi chạy
1. **Backend**:
   - Cài đặt thư viện: `pip install -r backend/requirements.txt`.
   - Chạy server: `python backend/app/main.py`.
2. **Frontend**:
   - Cài đặt thư viện: `corepack enable && yarn install --immutable`.
   - Chạy dev: `yarn dev` (Port 3001).

## Tiêu chuẩn Đánh giá
- Mọi lời gọi công cụ (tool calls) phải sử dụng Pydantic schema.
- Agent phải tuân thủ quy trình làm việc: **Nghiên cứu -> Chiến thuật -> Thực thi**.
- Logic đua xe quan trọng phải được xác thực bằng bộ dữ liệu "golden sets" trong `backend/eval/`.
