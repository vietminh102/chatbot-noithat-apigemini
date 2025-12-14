import time

import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os
import csv
from datetime import datetime

app = Flask(__name__)
CORS(app)


MY_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCm_lnruxp2gU69MmSamPhuhzwkXPPWKQI")
genai.configure(api_key=MY_API_KEY)

MODEL_LIST = [
    'models/gemini-2.5-flash',
    'models/gemini-2.5-flash-lite',
    'models/gemma-3-27b-it'
]


HISTORY_FILE = 'lich_su_chat_khach_hang.csv'



def khoi_tao_file_lich_su():
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['UserID', 'Time', 'Role', 'Content'])


def luu_tin_nhan_vao_csv(user_id, role, content):
    khoi_tao_file_lich_su()
    with open(HISTORY_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), role, content])


def lay_lich_su_tu_csv(user_id):
    if not os.path.exists(HISTORY_FILE):
        return ""

    try:

        df = pd.read_csv(HISTORY_FILE)

        df['UserID'] = df['UserID'].astype(str)
        user_history = df[df['UserID'] == str(user_id)]


        recent_history = user_history.tail(5)

        history_text = ""
        for _, row in recent_history.iterrows():
            role_name = "Khách hàng" if row['Role'] == 'user' else "Nhân viên tư vấn"
            history_text += f"{role_name}: {row['Content']}\n"

        return history_text
    except Exception as e:
        print(f"Lỗi đọc lịch sử: {e}")
        return ""


FILE_CSV = 'danh_sach_san_pham.csv'
df_products = pd.DataFrame()
product_list = ""

if os.path.exists(FILE_CSV):
    try:
        df_products = pd.read_csv(FILE_CSV)

        # Xử lý các cột thiếu
        if 'Link' not in df_products.columns: df_products['Link'] = ''
        if 'Discount' not in df_products.columns: df_products['Discount'] = 0

        df_products.fillna('', inplace=True)

        for _, row in df_products.iterrows():
            try:
                gia_goc = int(row['Price'])
            except:
                gia_goc = 0
            gia_fmt = f"{gia_goc:,}"


            link_info = f"[Link: {row['Link']}]" if row['Link'] else ""


            try:
                discount = int(row['Discount'])
            except:
                discount = 0


            if discount > 0:
                try:
                    gia_sau_giam = int(gia_goc * (100 - discount) / 100)
                    gia_sau_giam_fmt = f"{gia_sau_giam:,}"
                except:
                    gia_sau_giam_fmt = "???"


                status_tag = f"🔥 [ĐANG SALE {discount}% - CÒN: {gia_sau_giam_fmt} VNĐ]"
            else:

                status_tag = ""


            product_list += f"- Tên: {row['Name']} | Giá : {gia_fmt} VNĐ {status_tag} {link_info} | Mô tả: {row['Description']}\n"


    except Exception as e:
        print(f"❌ Lỗi đọc CSV: {e}")
else:
    print("⚠️ Không tìm thấy file danh_sach_san_pham.csv")


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
    max_retries = 3

    for attempt in range(max_retries):
        for model_name in MODEL_LIST:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Quota exceeded" in error_msg:
                    print(f"⚠️ Quá tải (429). Đang chờ 10s để thử lại... (Lần {attempt + 1})")
                    time.sleep(10)
                    break
                else:
                    print(f"❌ Lỗi model {model_name}: {e}")
                    continue
    raise Exception("Hệ thống AI đang quá tải, vui lòng thử lại sau 1 phút.")



@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    msg = data.get('message', '')

    user_id = data.get('user_id')
    if not user_id or user_id == "guest_unknown":
        user_id = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not msg: return jsonify({"reply": "..."})


    history_text_block = lay_lich_su_tu_csv(user_id)

    system_prompt = f"""
        VAI TRÒ: Bạn là nhân viên tư vấn chuyên nghiệp của Nội Thất Gỗ (NOITHATGO.VN).

        🛑 QUY TẮC TRẢ LỜI:
        - Dựa vào LỊCH SỬ CHAT để đưa ra câu trả lời có logic.
        - Khi khách hỏi về một loại sản phẩm (ví dụ "sofa", "bàn ăn"), hãy giới thiệu MỘT SỐ sản phẩm phù hợp trong danh sách "DỮ LIỆU KHO HÀNG" bên dưới.
        - KHÔNG được chỉ chăm chăm giới thiệu hàng đang SALE. Hãy giới thiệu cả hàng thường và hàng Sale một cách công bằng.
        - Nếu sản phẩm có thẻ [ĐANG SALE...], hãy báo giá đã giảm cho khách. Nếu không có thẻ đó, báo giá gốc.
        - Trả lời ngắn gọn, liệt kê các mẫu đẹp nhất.

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
        3. DỮ LIỆU KHO HÀNG (Tất cả sản phẩm)
        {product_list}

        4. LỊCH SỬ CHAT 
        {history_text_block}

        YÊU CẦU:
        - Khách hỏi gì đáp đúng câu hỏi của khách. 
        - Nếu khách hỏi "có sofa không", hãy liệt kê các mẫu sofa (kể cả không giảm giá).
        - Chỉ tập trung vào SALE khi khách hỏi "có khuyến mãi không".
        """

    try:
        full_prompt = f"{system_prompt}\n\nKhách hàng (mới nhất): {msg}\nNhân viên tư vấn:"
        reply = goi_ai_thong_minh(full_prompt)


        luu_tin_nhan_vao_csv(user_id, "user", msg)
        luu_tin_nhan_vao_csv(user_id, "bot", reply)
        return jsonify({"reply": reply})

    except Exception as e:
        print(f"❌ AI SẬP: {e}")
        tu_khoa = ""
        for k in ["sofa", "bàn", "ghế", "tủ", "giường", "kệ"]:
            if k in msg.lower(): tu_khoa = k; break

        fallback = "Hệ thống AI đang quá tải, em xin phép trả lời mặc định ạ.\n"
        if tu_khoa:
            kq = tim_kiem_thu_cong(tu_khoa)
            if kq:
                fallback += f"Em tìm thấy các mẫu '{tu_khoa}' này:\n{kq}"
            else:
                fallback += f"Em chưa thấy mẫu '{tu_khoa}' nào."
        else:
            fallback += "Anh/chị vui lòng gọi Hotline 0968.012.687 để được hỗ trợ ạ."

        return jsonify({"reply": fallback})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
