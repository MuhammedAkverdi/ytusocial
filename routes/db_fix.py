import sqlite3
import os

def veritabani_tamir_et():
    db_file = 'users.db'
    
    # Eğer users.db ana dizinde yoksa instance klasörüne bak
    if not os.path.exists(db_file):
        if os.path.exists('instance/users.db'):
            db_file = 'instance/users.db'
        else:
            print("❌ Hata: 'users.db' dosyası bulunamadı!")
            return

    print(f"🔧 '{db_file}' dosyası tamir ediliyor...")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 1. Comment tablosuna report_count ekle (Hata veren yer burası)
        try:
            cursor.execute("ALTER TABLE comment ADD COLUMN report_count INTEGER DEFAULT 0")
            print("✅ 'comment' tablosuna 'report_count' eklendi.")
        except sqlite3.OperationalError:
            print("ℹ️ 'comment.report_count' zaten var.")

        # 2. Post tablosuna report_count ekle (Garanti olsun)
        try:
            cursor.execute("ALTER TABLE post ADD COLUMN report_count INTEGER DEFAULT 0")
            print("✅ 'post' tablosuna 'report_count' eklendi.")
        except sqlite3.OperationalError:
            print("ℹ️ 'post.report_count' zaten var.")

        # 3. User tablosuna ban_expiration ekle
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN ban_expiration TIMESTAMP")
            print("✅ 'user' tablosuna 'ban_expiration' eklendi.")
        except sqlite3.OperationalError:
            print("ℹ️ 'user.ban_expiration' zaten var.")

        # 4. Message tablosuna reactions ekle
        try:
            cursor.execute("ALTER TABLE message ADD COLUMN reactions TEXT DEFAULT '{}'")
            print("✅ 'message' tablosuna 'reactions' eklendi.")
        except sqlite3.OperationalError:
            print("ℹ️ 'message.reactions' zaten var.")

        # 5. Message tablosuna msg_type ve file_path ekle (Eksikse diye kontrol)
        try:
            cursor.execute("ALTER TABLE message ADD COLUMN msg_type VARCHAR(10) DEFAULT 'text'")
            print("✅ 'message' tablosuna 'msg_type' eklendi.")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE message ADD COLUMN file_path VARCHAR(255)")
            print("✅ 'message' tablosuna 'file_path' eklendi.")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()
        print("\n🚀 TAMİR TAMAMLANDI! Şimdi 'python app.py' çalıştırabilirsin.")

    except Exception as e:
        print(f"❌ Beklenmedik hata: {e}")

if __name__ == "__main__":
    veritabani_tamir_et()