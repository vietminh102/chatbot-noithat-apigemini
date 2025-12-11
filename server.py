import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os

app = Flask(__name__)
CORS(app)


MY_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCm_lnruxp2gU69MmSamPhuhzwkXPPWKQI")
genai.configure(api_key=MY_API_KEY)

MODEL_LIST = [
    'models/gemini-2.5-flash',
    'models/gemini-2.5-flash-lite',
    'models/gemma-3-27b-it'
]


chat_history_storage = {}


FILE_CSV = 'danh_sach_san_pham.csv'
df_products = pd.DataFrame()
kho_hang_text = ""

if os.path.exists(FILE_CSV):
    try:
        df_products = pd.read_csv(FILE_CSV)
        if 'Link' not in df_products.columns: df_products['Link'] = ''

        df_products.fillna('', inplace=True)

        for _, row in df_products.iterrows():
            try:
                gia = f"{int(row['Price']):,}"
            except:
                gia = row['Price']

            link_info = f"| Link: {row['Link']}" if row['Link'] else ""

            kho_hang_text += f"- {row['Name']} | Giá: {gia} VNĐ {link_info} | {row['Description']}\n"

    except Exception as e:
        print(f"❌ Lỗi CSV: {e}")


def tim_kiem_thu_cong(tu_khoa):
    if df_products.empty: return ""
    tu_khoa = tu_khoa.lower()
    mask = (df_products['Name'].str.lower().str.contains(tu_khoa, na=False) |
            df_products['Description'].str.lower().str.contains(tu_khoa, na=False))
    ket_qua = df_products[mask].head(5)
    ds = []
    for _, row in ket_qua.iterrows():
        try:
            gia = f"{int(row['Price']):,}"
        except:
            gia = row['Price']
        link_str = f"- Link: {row['Link']}" if row['Link'] else ""
        ds.append(f"- {row['Name']} (Giá: {gia} VNĐ) {link_str}")
    return "\n".join(ds)


def goi_ai_thong_minh(prompt):
    loi_cuoi = ""
    for model_name in MODEL_LIST:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            loi_cuoi = str(e)
            continue
    raise Exception(loi_cuoi)


@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    msg = data.get('message', '')
    if not msg: return jsonify({"reply": "..."})


    user_id = request.headers.get('X-Forwarded-For', request.remote_addr)

    if user_id not in chat_history_storage:
        chat_history_storage[user_id] = []

    recent_history = chat_history_storage[user_id][-12:]
    history_text_block = ""
    for turn in recent_history:
        role = "Khách hàng" if turn['role'] == 'user' else "Nhân viên tư vấn"
        history_text_block += f"{role}: {turn['content']}\n"

    system_prompt = f"""
        Bạn là trí tuệ nhân tạo tư vấn của website Nội Thất Gỗ (NOITHATGO.VN).

        1. THÔNG TIN CỬA HÀNG (Dùng để trả lời khi khách hỏi địa chỉ, liên hệ):
        - Hotline Mua Hàng / CSKH: 0968 012 687
        - Email hỗ trợ: mviet1304@gmail.vn
        - Website: noithatgo.vn
        - Địa chỉ showroom: 1234 đường Láng, Cầu Giấy, Hà Nội
        - Giờ làm việc: 8h00 - 21h00 tất cả các ngày trong tuần.

        2. CHÍNH SÁCH BÁN HÀNG (Trả lời khi khách hỏi ship, bảo hành):
        - Vận chuyển: Miễn phí nội thành, ngoại thành tính phí theo đơn vị vận chuyển.
        - Bảo hành: Sản phẩm gỗ bảo hành 12 tháng, bảo trì trọn đời.
        - Trong Hà Nội vận chuyển  và lắp đặt trong ngày, các tỉnh khác vận chuyển 2-3 ngày

        3. DANH SÁCH SẢN PHẨM TRONG KHO:
        --------------------------------------
        {kho_hang_text}
        --------------------------------------
        4. LỊCH SỬ TRÒ CHUYỆN VỪA QUA (HÃY ĐỌC KỸ ĐỂ HIỂU NGỮ CẢNH):
        --------------------------------------
        {history_text_block}
        --------------------------------------

        NHIỆM VỤ CỦA BẠN:
        - Trả lời ngắn gọn, lịch sự, xưng hô là "em" và gọi 'anh/chị'.
        - Nếu khách hỏi liên hệ/địa chỉ, hãy lấy thông tin ở mục 1.
        - Dựa vào 'LỊCH SỬ TRÒ CHUYỆN', hãy trả lời câu hỏi mới nhất của khách một cách logic, liền mạch.
        - Ví dụ: Khách hỏi "Cái đó giá bao nhiêu", bạn phải nhìn lịch sử xem "Cái đó" là cái gì.
        - Nếu khách hỏi sản phẩm, hãy tra cứu ở mục 3.
        - Tuyệt đối trung thực, không bịa đặt thông tin không có trong danh sách.
        - Lưu ý chỉ 'chào ...' lần đầu tiên khi bắt đầu hội thoại.
        """


    try:
        full_prompt = f"{system_prompt}\n\nKhách hàng (mới nhất): {msg}\nNhân viên tư vấn:"
        reply = goi_ai_thong_minh(full_prompt)


        chat_history_storage[user_id].append({"role": "user", "content": msg})
        chat_history_storage[user_id].append({"role": "bot", "content": reply})
        return jsonify({"reply": reply})

    except Exception as e:
        print(f"❌ AI SẬP: {e}")
        tu_khoa = ""
        for k in ["sofa", "bàn", "ghế", "tủ", "giường", "kệ"]:
            if k in msg.lower(): tu_khoa = k; break

        fallback = "Hệ thống AI đang quá tải, Đây là tin nhắn mặc định ạ.\n"
        if tu_khoa:
            kq = tim_kiem_thu_cong(tu_khoa)
            if kq:
                fallback += f"Em tìm thấy các mẫu '{tu_khoa}' này:\n{kq}"
            else:
                fallback += f"Em chưa thấy mẫu '{tu_khoa}' nào trong kho ạ."
        else:
            fallback += "Anh/chị vui lòng gọi Hotline 0968.012.687 để được hỗ trợ nhanh nhất ạ."

        return jsonify({"reply": fallback})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
