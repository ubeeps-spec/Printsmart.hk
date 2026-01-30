# E-Shop Project

這是一個使用 Django 開發的電子商務網站專案。

## 如何開始 (Setup)

1. **複製專案 (Clone)**
   ```bash
   git clone <your-repo-url>
   cd e-shop
   ```

2. **建立虛擬環境 (Virtual Environment)**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **安裝依賴套件 (Install Dependencies)**
   ```bash
   pip install -r requirements.txt
   ```

4. **資料庫遷移 (Migrations)**
   ```bash
   python manage.py migrate
   ```

5. **建立超級使用者 (Create Superuser)**
   ```bash
   python manage.py createsuperuser
   ```

6. **啟動伺服器 (Run Server)**
   ```bash
   python manage.py runserver
   ```

## 注意事項 (測試版說明)
- **資料庫**: 此測試版本 **已包含** `db.sqlite3`，下載後可直接使用現有資料，無需重新遷移 (migrate)。
- **媒體檔案**: 此測試版本 **已包含** `media/` 資料夾，下載後可直接看到商品圖片與 Banner。
- **帳號資訊**: 請參考專案內部的說明文件或直接詢問管理員。
