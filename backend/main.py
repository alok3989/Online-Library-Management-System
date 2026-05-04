from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import engine, Base, get_db
import models
from pydantic import BaseModel
from typing import Optional, List
import jwt
from datetime import datetime, timedelta
import os
from security import verify_password, get_password_hash

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="LibraTech API - Phase 2")

# Configure CORS for production and development
FRONTEND_URL = os.environ.get("FRONTEND_URL", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up local directory for serving PDFs as requested
os.makedirs("static/pdfs", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-key-for-libratech")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# --- Startup Event (Auto-Seed for Cloud) ---

@app.on_event("startup")
def startup_event():
    db = get_db().__next__()
    try:
        from security import get_password_hash
        
        # 1. Ensure Admin exists
        admin = db.query(models.User).filter(models.User.name == "admin").first()
        if not admin:
            admin = models.User(user_id="u-admin-001", name="admin", password_hash=get_password_hash("password123"), role=models.RoleEnum.admin)
            db.add(admin)
            print("Admin created.")

        # 2. Ensure Students exist
        students_data = [
            ("student", "student123", "u-student-001"),
            ("alok", "alok123", "u-student-002"),
            ("rahul", "rahul123", "u-student-003"),
            ("priya", "priya123", "u-student-004"),
        ]
        
        for name, pwd, uid in students_data:
            existing = db.query(models.User).filter(models.User.name == name).first()
            if not existing:
                new_user = models.User(user_id=uid, name=name, password_hash=get_password_hash(pwd), role=models.RoleEnum.student)
                db.add(new_user)
                print(f"Student {name} created.")

        # 3. Ensure Sample Books exist if catalog is empty
        if db.query(models.Book).count() == 0:
            books = [
                models.Book(isbn="978-0-262-03384-8", title="Introduction to Algorithms", category="Computer Science", format=models.FormatEnum.physical),
                models.Book(isbn="978-0-13-235088-4", title="Computer Networks", category="Computer Science", format=models.FormatEnum.physical)
            ]
            db.add_all(books)
            print("Sample books seeded.")
            
        db.commit()
        print("Startup sync complete.")
    except Exception as e:
        print(f"Startup seed error: {e}")
    finally:
        db.close()

# --- Pydantic Schemas ---

class LoginRequest(BaseModel):
    member_id: str
    password: str

class UserCreate(BaseModel):
    name: str
    password: str
    role: str # 'student' or 'admin'

class ChatRequest(BaseModel):
    message: str

class BookCreate(BaseModel):
    isbn: str
    title: str
    category: str
    format: str # 'physical' or 'digital'

class BookOut(BaseModel):
    isbn: str
    title: str
    category: Optional[str] = None
    format: str
    status: str

class TransactionOut(BaseModel):
    transaction_id: str
    isbn: str
    book_title: str
    issue_date: str
    due_date: str
    status: str

class DashboardStats(BaseModel):
    books_issued: int
    overdue_count: int
    total_fines: float
    user_name: str
    user_role: str
    trust_score: int

# --- Auth Helpers ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(authorization: str = Header(...), db: Session = Depends(get_db)):
    """Decode JWT from the Authorization header and return the User object."""
    try:
        # Expect "Bearer <token>"
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token missing user_id")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except (jwt.DecodeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def check_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin access denied")
    return current_user

# --- Health Check (For Zero-Downtime Deployment) ---

@app.get("/api/health")
def health_check():
    """Endpoint for cloud providers to verify server status."""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

# --- Endpoints ---

@app.post("/token")
def login_for_access_token(request: LoginRequest, db: Session = Depends(get_db)):
    # Note: For prototype simplicity, matching member_id with name
    user = db.query(models.User).filter(models.User.name == request.member_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials!",
        )

    # Check if user is locked out
    if user.lockout_until:
        if user.lockout_until > datetime.utcnow():
            remaining_time = user.lockout_until - datetime.utcnow()
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account blocked for 24 hours due to 2 failed attempts. Please contact admin.",
            )
        else:
            # Lockout period expired, reset attempts for a fresh start
            user.failed_login_attempts = 0
            user.lockout_until = None
            db.commit()

    # Verify password using bcrypt
    if not verify_password(request.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 2:
            user.lockout_until = datetime.utcnow() + timedelta(hours=24)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Too many failed attempts. Account blocked for 24 hours. Contact admin.",
            )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Credentials! (Attempt {user.failed_login_attempts}/2)",
        )

    # Success: Reset failed attempts and lockout
    user.failed_login_attempts = 0
    user.lockout_until = None
    db.commit()

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.name, "role": user.role.value, "user_id": user.user_id},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user.role.value}


@app.get("/api/dashboard/stats")
def get_dashboard_stats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected endpoint: returns dashboard stats for the logged-in user."""
    issued_count = db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.user_id,
        models.Transaction.status == models.TransactionStatusEnum.active
    ).count()

    overdue_count = db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.user_id,
        models.Transaction.status == models.TransactionStatusEnum.overdue
    ).count()

    # Fine calculation: ₹10 per overdue book (simplified for prototype)
    total_fines = overdue_count * 10.0

    return {
        "books_issued": issued_count,
        "overdue_count": overdue_count,
        "total_fines": total_fines,
        "user_name": current_user.name,
        "user_role": current_user.role.value,
        "trust_score": current_user.trust_score,
    }

@app.post("/api/fines/pay")
def pay_fines(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Simulate paying all fines: marks all overdue books as returned."""
    overdue_txns = db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.user_id,
        models.Transaction.status == models.TransactionStatusEnum.overdue
    ).all()
    
    for txn in overdue_txns:
        txn.status = models.TransactionStatusEnum.returned
        txn.return_date = datetime.utcnow()
        # Make the book available again
        book = db.query(models.Book).filter(models.Book.isbn == txn.isbn).first()
        if book: book.status = models.StatusEnum.available
    
    db.commit()
    return {"message": f"All fines paid successfully! {len(overdue_txns)} books cleared."}


@app.get("/api/books")
def get_all_books(db: Session = Depends(get_db)):
    """Public endpoint: returns all books in the catalog."""
    books = db.query(models.Book).all()
    result = []
    for book in books:
        result.append({
            "isbn": book.isbn,
            "title": book.title,
            "category": book.category or "General",
            "format": book.format.value,
            "status": book.status.value,
        })
    return result


@app.get("/api/transactions/me")
def get_my_transactions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected endpoint: returns issued/overdue books for the logged-in user."""
    transactions = db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.user_id,
        models.Transaction.status.in_([
            models.TransactionStatusEnum.active,
            models.TransactionStatusEnum.overdue,
        ])
    ).all()

    result = []
    for txn in transactions:
        book = db.query(models.Book).filter(models.Book.isbn == txn.isbn).first()
        result.append({
            "transaction_id": txn.transaction_id,
            "isbn": txn.isbn,
            "book_title": book.title if book else "Unknown",
            "book_category": book.category if book else "",
            "issue_date": txn.issue_date.strftime("%d %b %Y") if txn.issue_date else "-",
            "due_date": txn.due_date.strftime("%d %b %Y") if txn.due_date else "-",
            "status": txn.status.value,
        })
    return result


@app.post("/api/transactions/issue/{isbn}")
def issue_book(
    isbn: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected endpoint: issue an available book to the logged-in user."""
    # Check for overdue books or unpaid fines
    overdue_count = db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.user_id,
        models.Transaction.status == models.TransactionStatusEnum.overdue
    ).count()
    
    if overdue_count > 0:
        raise HTTPException(status_code=403, detail=f"You have {overdue_count} overdue book(s). Please return them and pay your fines before issuing new books.")

    # 1. Look up the book
    book = db.query(models.Book).filter(models.Book.isbn == isbn).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # 2. Ensure the book is available
    if book.status != models.StatusEnum.available:
        raise HTTPException(status_code=400, detail="Book not available")

    # 3. Determine if approval is needed (only for physical books)
    is_physical = book.format == models.FormatEnum.physical
    target_status = models.TransactionStatusEnum.pending_issue if is_physical else models.TransactionStatusEnum.active
    
    # 4. Update book status (reserved if pending, issued if instant)
    if is_physical:
        book.status = models.StatusEnum.reserved
    else:
        book.status = models.StatusEnum.issued

    # 5. Create the transaction
    today = datetime.utcnow()
    new_txn = models.Transaction(
        user_id=current_user.user_id,
        isbn=isbn,
        issue_date=today,
        due_date=today + timedelta(days=14),
        status=target_status,
    )
    db.add(new_txn)
    db.commit()

    if is_physical:
        return {"message": f"Request to borrow '{book.title}' sent to Admin for approval."}
    return {"message": f"'{book.title}' (Digital) borrowed successfully!"}


@app.post("/api/transactions/return/{isbn}")
def return_book(
    isbn: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected endpoint: return an issued book for the logged-in user."""
    # 1. Find the active transaction for this user + isbn
    txn = db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.user_id,
        models.Transaction.isbn == isbn,
        models.Transaction.status.in_([
            models.TransactionStatusEnum.active,
            models.TransactionStatusEnum.overdue,
        ])
    ).first()

    if not txn:
        raise HTTPException(status_code=400, detail="No active transaction found for this book")

    # 2. Update status based on format
    # Look up the book to check format
    book = db.query(models.Book).filter(models.Book.isbn == isbn).first()
    
    if book and book.format == models.FormatEnum.physical:
        # Physical books need admin to confirm they are back
        txn.status = models.TransactionStatusEnum.pending_return
        # Also update book status so catalog reflects it's not "Issued"
        book.status = models.StatusEnum.available 
        db.commit()
        return {"message": "Return request sent! Please hand the book to the librarian for final approval."}
    else:
        # Digital books or fallback: instant return
        txn.status = models.TransactionStatusEnum.returned
        txn.return_date = datetime.utcnow()
        if book:
            book.status = models.StatusEnum.available
        db.commit()
        return {"message": "Book returned successfully!"}


# --- AI Academic Assistant (Phase 4) ---
LIBRATECH_SYSTEM_PROMPT = """You are the LibraTech AI Academic Tutor — an intelligent assistant embedded in a university library management system.

Your capabilities:
- Summarize book chapters and academic papers
- Explain complex concepts in Computer Science, Mathematics, Software Engineering, AI/ML, and Web Development
- Help students understand their coursework and solve academic doubts
- Recommend books from the library catalog based on a student's query
- Provide study tips and learning strategies

Rules:
- Be concise but thorough (2-4 paragraphs max unless asked for more)
- Use markdown formatting for clarity (bold, bullet points, code blocks)
- Stay strictly academic — do not help with non-academic queries
- Always be encouraging and supportive
- If you don't know something, say so honestly
"""

# Try to initialize Gemini client
gemini_model = None
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

try:
    if GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=LIBRATECH_SYSTEM_PROMPT
        )
        print("✅ LibraTech AI Tutor: GEMINI LIVE MODE ACTIVE")
except Exception as e:
    print(f"⚠️ LibraTech AI Tutor: Gemini Initialization Failed (Reason: {e})")

# Try to initialize Groq client
groq_client = None
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

try:
    if GROQ_API_KEY:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
        print("✅ LibraTech AI Tutor: GROQ LIVE MODE ACTIVE")
except Exception as e:
    print(f"⚠️ LibraTech AI Tutor: Groq Initialization Failed (Reason: {e})")


OFFLINE_RESPONSES = {
    "default": "👋 I'm the **LibraTech AI Tutor** running in offline prototype mode.\n\nIn production, I would:\n- Summarize chapters and research papers\n- Solve your academic doubts step-by-step\n- Recommend books from our catalog\n\nConnect a Gemini API key to unlock full AI capabilities!",
    "summarize": "📖 **Chapter Summary (Prototype)**\n\nIn production mode, I would analyze the full text and provide:\n- A concise 3-paragraph summary\n- Key takeaways and important definitions\n- Related topics for further reading\n\nSet the `GEMINI_API_KEY` environment variable to enable this feature.",
    "algorithm": "🧮 **Algorithm Explanation (Prototype)**\n\nI'd break down the algorithm into:\n1. **Time Complexity** analysis with Big-O notation\n2. **Step-by-step walkthrough** with examples\n3. **Python/pseudocode** implementation\n4. **Common pitfalls** and optimization tips\n\nThis is a simulated response — connect the Gemini API for real answers!",
    "recommend": "📚 **Book Recommendation (Prototype)**\n\nBased on your query, I would search our catalog and suggest:\n- **Primary picks** matching your topic\n- **Supplementary reads** for deeper understanding\n- **Available e-books** for instant access\n\nEnable the AI backend for personalized recommendations!",
}

def get_offline_response(message: str) -> str:
    msg = message.lower()
    if any(w in msg for w in ["summarize", "summary", "chapter", "explain this"]):
        return OFFLINE_RESPONSES["summarize"]
    if any(w in msg for w in ["algorithm", "sort", "search", "complexity", "big o", "data structure"]):
        return OFFLINE_RESPONSES["algorithm"]
    if any(w in msg for w in ["recommend", "suggest", "book", "read", "reference"]):
        return OFFLINE_RESPONSES["recommend"]
    return OFFLINE_RESPONSES["default"]


@app.post("/api/chat")
async def chat_with_ai(
    request: ChatRequest,
    current_user: models.User = Depends(get_current_user),
):
    """Protected endpoint: AI Academic Assistant chat."""
    user_message = request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # 1. Try Groq API
    if groq_client:
        try:
            target_model = "llama-3.3-70b-versatile"
            print(f"DEBUG: Attempting Groq AI generation using model: {target_model}")
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": LIBRATECH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                model=target_model,
            )
            return {"reply": chat_completion.choices[0].message.content}
        except Exception as e:
            print(f"❌ Groq Generation Failed: {e}")
            # Don't return yet, try Gemini next

    # 2. Try Gemini API
    if gemini_model:
        try:
            print("DEBUG: Attempting Gemini AI generation")
            response = gemini_model.generate_content(user_message)
            return {"reply": response.text}
        except Exception as e:
            print(f"❌ Gemini Generation Failed: {e}")

    # 3. Offline fallback
    return {"reply": get_offline_response(user_message)}

# --- ADMIN ENDPOINTS ---

@app.post("/api/admin/books")
def admin_add_book(book_in: BookCreate, admin: models.User = Depends(check_admin), db: Session = Depends(get_db)):
    # Check if book already exists
    existing = db.query(models.Book).filter(models.Book.isbn == book_in.isbn).first()
    if existing:
        raise HTTPException(status_code=400, detail="Book with this ISBN already exists")
    
    new_book = models.Book(
        isbn=book_in.isbn,
        title=book_in.title,
        category=book_in.category,
        format=models.FormatEnum[book_in.format],
        status=models.StatusEnum.available
    )
    db.add(new_book)
    db.commit()
    return {"message": f"Book '{book_in.title}' added successfully"}

@app.delete("/api/admin/books/{isbn}")
def admin_delete_book(isbn: str, admin: models.User = Depends(check_admin), db: Session = Depends(get_db)):
    book = db.query(models.Book).filter(models.Book.isbn == isbn).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Check if book is currently issued
    if book.status.value == "issued":
        raise HTTPException(status_code=400, detail="Cannot delete an issued book")

    db.delete(book)
    db.commit()
    return {"message": "Book deleted successfully"}

@app.get("/api/admin/requests")
def admin_get_pending_requests(admin: models.User = Depends(check_admin), db: Session = Depends(get_db)):
    """Admin-only: list all transactions waiting for approval."""
    try:
        txns = db.query(models.Transaction).filter(
            models.Transaction.status.in_([
                models.TransactionStatusEnum.pending_issue,
                models.TransactionStatusEnum.pending_return
            ])
        ).all()
        
        results = []
        for t in txns:
            user = db.query(models.User).filter(models.User.user_id == t.user_id).first()
            book = db.query(models.Book).filter(models.Book.isbn == t.isbn).first()
            
            # Clean status string
            status_str = t.status.value if hasattr(t.status, 'value') else str(t.status)
            if "." in status_str: status_str = status_str.split(".")[-1]

            results.append({
                "transaction_id": t.transaction_id,
                "user_name": user.name if user else "Unknown",
                "book_title": book.title if book else "Unknown",
                "isbn": t.isbn,
                "status": status_str,
                "date": t.issue_date
            })
        return results
    except Exception as e:
        print(f"ERROR in admin_get_pending_requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/transactions")
def admin_get_all_transactions(admin: models.User = Depends(check_admin), db: Session = Depends(get_db)):
    transactions = db.query(models.Transaction).all()
    results = []
    for tx in transactions:
        user = db.query(models.User).filter(models.User.user_id == tx.user_id).first()
        book = db.query(models.Book).filter(models.Book.isbn == tx.isbn).first()
        results.append({
            "transaction_id": tx.transaction_id,
            "user_name": user.name if user else "Unknown",
            "book_title": book.title if book else "Unknown",
            "isbn": tx.isbn,
            "issue_date": tx.issue_date.strftime("%Y-%m-%d"),
            "due_date": tx.due_date.strftime("%Y-%m-%d"),
            "status": tx.status.value
        })
    return results

@app.post("/api/admin/approve/{transaction_id}")
def admin_process_request(transaction_id: str, action: str, admin: models.User = Depends(check_admin), db: Session = Depends(get_db)):
    """Admin-only: Approve or Reject a pending transaction."""
    txn = db.query(models.Transaction).filter(models.Transaction.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    book = db.query(models.Book).filter(models.Book.isbn == txn.isbn).first()

    if action == "approve":
        if txn.status == models.TransactionStatusEnum.pending_issue:
            txn.status = models.TransactionStatusEnum.active
            if book: book.status = models.StatusEnum.issued
        elif txn.status == models.TransactionStatusEnum.pending_return:
            txn.status = models.TransactionStatusEnum.returned
            if book: book.status = models.StatusEnum.available
        
        db.commit()
        return {"message": f"Transaction {action}d successfully"}
        
    elif action == "reject":
        if txn.status == models.TransactionStatusEnum.pending_issue:
            if book: book.status = models.StatusEnum.available
        elif txn.status == models.TransactionStatusEnum.pending_return:
            if book: book.status = models.StatusEnum.issued
            
        db.delete(txn)
        db.commit()
        return {"message": "Request rejected and removed."}

    raise HTTPException(status_code=400, detail="Invalid action")

@app.post("/api/admin/users")
def admin_create_user(user_in: UserCreate, admin: models.User = Depends(check_admin), db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.name == user_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this name already exists")
    
    new_user = models.User(
        name=user_in.name,
        password_hash=get_password_hash(user_in.password),
        role=models.RoleEnum[user_in.role]
    )
    db.add(new_user)
    db.commit()
    return {"message": f"User '{user_in.name}' created successfully"}



# --- Serve Frontend HTML Pages ---
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..")

@app.get("/")
def serve_login():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/dashboard.html")
def serve_dashboard():
    return FileResponse(os.path.join(FRONTEND_DIR, "dashboard.html"))

# Serve frontend static assets (style.css, script.js) from the parent directory
app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
