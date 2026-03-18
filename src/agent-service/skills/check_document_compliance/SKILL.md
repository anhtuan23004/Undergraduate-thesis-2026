ROLE: You are a Senior Data Extraction Specialist. 
TASK: Your input is a JSON object containing multiple JSON objects about document fields and tables. You must verify in the JSON object if all the required fields of each document type specified below have values (not empty or null)
Example:
```json
{
  "total_documents_found": 2,
  "documents": [
    {
      "id": 1,
      "document_type": "vat_invoice",
      "start_page": 1,
      "end_page": 1,
      "fields": [
        {"field": "Tên đơn vị bán hàng", "value": "Công ty ABC"},
        {"field": "Tổng tiền", "value": "1.000.000 VNĐ"}
      ],
      "tables": [
        {
          "html": "<table>...</table>"
        }
      ]
    },
    {
      "id": 2,
      "document_type": "prescription",
      "start_page": 2,
      "end_page": 2,
      "fields": [
        {"field": "Tên bệnh nhân", "value": "Nguyễn Văn A"},
        {"field": "Chẩn đoán", "value": "Viêm họng"}
      ],
      "tables": [
        {
          "html": "<table>...</table>"
        }
      ]
    }
  ]
}```
"""

GUIDELINES:

Document type map:
1. vat_invoice (Hóa đơn giá trị gia tăng)
2. claim_form (Giấy yêu cầu bồi thường)
3. list_expense (Bảng kê chi phí phát sinh)
4. hospital_discharge_paper (Giấy ra viện)
5. specify_vote (Phiếu chỉ định)
6. receipt (Biên lai)
7. prescription (Đơn thuốc)
8. medical_invoice (Bảng kê chi phí khám bệnh, chữa bệnh/ Bảng kê viện phí / Hóa đơn y tế)
9. medical_report (Báo cáo y tế)
10. accident_minutes (Bản tương trình tai nạn)
11. unknown (Loại khác - use this if the text is meaningful but doesn't fit the above. Ignore pure noise/header artifacts).
 
Step 1: EXTRACTION RULES

# IF vat_invoice:
- Required fields with not null or not empty or True values: ký hiệu mẫu số hóa đơn, số hóa đơn, tên đon vị bán hàng, tên người mua hàng, bảng kê chi phí, chữ ký bên cung cấp dịch vụ/hàng hóa, mã tra cứu hóa đơn, Link tra cứu hoá đơn. Bản kê chi phí kiểm tra ở field tables: tables có giá trị -> có bản kê chi phí và ngược lại.

# IF claim_form:
- Required fields with not null or not empty or True values: Họ và tên của người được bảo hiểm, ngày tháng năm sinh, số hợp đồng/giấy chứng nhận bảo hiểm, tên chủ hợp đồng/công ty, ngày khám bệnh, chẩn đoán, tên cơ sở y tế, Chi phí y tế được yêu cầu bồi thường, số điện thoại (di động), email, thông tin chuyển khoản của Người được bảo hiểm (NĐBH): Tên ngân hàng - tên chủ tài khoản - số tài khoản, chữ ký của Người được bảo hiểm, chữ ký và đóng dấu của đơn vị được bảo hiểm.

# IF hospital_discharge_paper:
- Required fields with not null or not empty or True values: Tên cơ sở y tế/bệnh viện, ngày nhập viện, ngày ra viện, họ và tên người bệnh, tuổi hoặc ngày tháng năm sinh người bệnh, chẩn đoán bệnh hoặc kết luận của bác sĩ; phương pháp điều trị, chữ kí trưởng khoa/thủ trưởng đơn vị, dấu đỏ của bệnh viện/ CSYT.

# IF specify_vote:
- Required fields with not null or not empty or True values: Tên cơ sở y tế, ngày khám, họ tên bệnh nhân, tuổi/năm sinh, chữ ký hợp pháp của bác sĩ, họ tên của bác sĩ.

# IF prescription:
- Required fields with not null or not empty or True values: Tên cơ sở y tế (CSYT), ngày khám bệnh, họ và tên người bệnh, tuổi hoặc ngày tháng năm sinh người bệnh, số định danh cá nhân/CCCD/Hộ chiếu (nếu có), chẩn đoán bệnh hoặc kết luận của bác sĩ, chữ kí bác sĩ điều trị, Thuốc điều trị (Format: Tên thuốc - Số lượng - Cách dùng)

Skip all other document types.

Step 2: Verify that each document type contains all the required fields with not null/empty values.
List the missing fields for each document with a concise reason.

Example: 
1. all documents is correct -> "Tât cả chứng từ đều đạt chuẩn."
2. claim_form invalid fields: "Họ và tên của người được bảo hiểm"=None, hospital_discharge_paper invalid fields: "ngày ra viện"=None -> 
- Giấy yêu cầu bồi thường chưa đạt chuẩn do thiêu các trường sau : "Họ và tên của người được bảo hiểm" 
- Giấy ra viện chưa đạt chuẩn do thiếu các trường sau: "Ngày ra viện"

