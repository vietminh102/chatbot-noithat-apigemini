import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os

app = Flask(__name__)
CORS(app)


# CẤU HÌNH API
MY_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCm_lnruxp2gU69MmSamPhuhzwkXPPWKQI")
genai.configure(api_key=MY_API_KEY)


MODEL_LIST = [
    'models/gemini-2.5-flash',
    'models/gemini-2.5-flash-lite',
    'models/gemma-3-27b-it'
]



FILE_CSV = 'danh_sach_san_pham.csv'
df_products = pd.DataFrame()
kho_hang_text = ""

if os.path.exists(FILE_CSV):
    try:
        df_products = pd.read_csv(FILE_CSV)
        # Tạo văn bản cho AI đọc
        for _, row in df_products.iterrows():
            try:
                gia = f"{int(row['Price']):,}"
            except:
                gia = row['Price']
            kho_hang_text += f"- {row['Name']} | Giá: {gia} VNĐ | {row['Description']}\n"

        # Xử lý dữ liệu trống cho tìm kiếm thủ công
        df_products.fillna('', inplace=True)
        print(f"✅ Đã nạp {len(df_products)} sản phẩm.")
    except Exception as e:
        print(f"❌ Lỗi CSV: {e}")


# 3. HÀM TÌM KIẾM THỦ CÔNG
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
        ds.append(f"- {row['Name']} (Giá: {gia} VNĐ)")
    return "\n".join(ds)



# HÀM GỌI AI ĐA LUỒNG
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



# XỬ LÝ CHAT CHÍNH
@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    msg = data.get('message', '')
    if not msg: return jsonify({"reply": "..."})

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

        3. DANH SÁCH SẢN PHẨM TRONG KHO:
        --------------------------------------
        {kho_hang_text}
        --------------------------------------

        NHIỆM VỤ CỦA BẠN:
        - Trả lời ngắn gọn, lịch sự, xưng hô là "em" hoặc "mình", chỉ lặp lại 'chào anh/chị ...' khi bắt đầu
        cuộc hội thoại hoặc khách hàng chào.
        - Nếu khách hỏi liên hệ/địa chỉ, hãy lấy thông tin ở mục 1.
        - Nhớ câu hỏi của khách hàng để trả lời cho câu sau
        - Nếu khách hỏi sản phẩm, hãy tra cứu ở mục 3.
        - Tuyệt đối trung thực, không bịa đặt thông tin không có trong danh sách.
        """



    try:
        reply = goi_ai_thong_minh(f"{system_prompt}\n\nKhách: {msg}")
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
