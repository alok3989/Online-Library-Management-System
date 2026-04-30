from database import SessionLocal
import models

def check():
    db = SessionLocal()
    try:
        txns = db.query(models.Transaction).all()
        print(f"\n--- DATABASE INSPECTION ({len(txns)} Transactions) ---")
        for t in txns:
            # Using transaction_id because models.py defines it that way
            print(f"TX_ID: {t.transaction_id[:8]} | User: {t.user_id} | ISBN: {t.isbn} | Status: {t.status}")
        
        books = db.query(models.Book).all()
        print(f"\n--- BOOK STATUSES ---")
        for b in books:
            print(f"Title: {b.title[:20]} | Status: {b.status} | Format: {b.format}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check()
