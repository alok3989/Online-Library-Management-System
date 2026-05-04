const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:')
    ? `http://localhost:8000`
    : 'https://libratech-backend-kcnv.onrender.com';

// --- Utility: Get auth headers ---
function authHeaders() {
    const token = localStorage.getItem('access_token');
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };
}

// --- Utility: Authenticated fetch with auto-redirect on 401 ---
async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const defaults = { headers: authHeaders() };
    const response = await fetch(url, { ...defaults, ...options });
    if (response.status === 401) {
        // Token expired or invalid — force logout
        localStorage.clear();
        window.location.href = 'index.html';
        return null;
    }
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `API Error: ${response.status}`);
    }
    return response.json();
}

document.addEventListener('DOMContentLoaded', function() {

    // --- SESSION GUARD (For Dashboard) ---
    const isDashboard = window.location.pathname.includes('dashboard.html');
    if (isDashboard && !localStorage.getItem('access_token')) {
        window.location.href = 'index.html';
        return;
    }

    // --- 1. LOGIN LOGIC & TOAST NOTIFICATIONS ---
    const loginForm = document.querySelector('.login-form');

    if(loginForm) {
        loginForm.addEventListener('submit', function(event) {
            event.preventDefault();

            const memberId = document.getElementById('member-id').value;
            const password = document.getElementById('password').value;
            const loginBtn = document.querySelector('.btn-login');

            const originalText = loginBtn.innerHTML;
            loginBtn.innerHTML = 'Signing In... <i class="fa-solid fa-spinner fa-spin"></i>';
            loginBtn.disabled = true;

            fetch(`${API_BASE}/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ member_id: memberId, password: password })
            })
            .then(async response => {
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || "Invalid Credentials!");
                }
                return response.json();
            })
            .then(data => {
                // Store JWT in localStorage
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('user_role', data.role);
                localStorage.setItem('user_name', memberId);

                showToast("Login Successful! Redirecting...", "success");
                setTimeout(() => window.location.href = "dashboard.html", 800);
            })
            .catch(error => {
                showToast(error.message, "error");
                loginBtn.innerHTML = originalText;
                loginBtn.disabled = false;
            });
        });
    }

    // --- 2. DYNAMIC GREETING (Dashboard Only) ---
    function updateGreeting() {
        const greetingElement = document.getElementById('dynamic-greeting');
        if (greetingElement) {
            const hour = new Date().getHours();
            let greeting = "Good evening";
            if (hour < 12) greeting = "Good morning";
            else if (hour < 18) greeting = "Good afternoon";
            greetingElement.innerText = greeting;
        }
    }
    updateGreeting();

    // --- 3. MOBILE SIDEBAR TOGGLE ---
    const menuToggle = document.getElementById('menuToggle');
    const closeSidebar = document.getElementById('closeSidebar');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    function toggleSidebar() {
        if(sidebar && overlay) {
            sidebar.classList.toggle('active');
            overlay.classList.toggle('active');
        }
    }

    if (menuToggle && closeSidebar && sidebar && overlay) {
        menuToggle.addEventListener('click', toggleSidebar);
        closeSidebar.addEventListener('click', toggleSidebar);
        overlay.addEventListener('click', toggleSidebar);
    }
    // --- 4. SPA ROUTING (Switching Views) ---
    const pageTitle = document.getElementById('page-title');
    const userName = localStorage.getItem('user_name') || 'User';
    
    document.addEventListener('click', function(e) {
        const item = e.target.closest('.nav-item');
        if (!item) return;

        e.preventDefault();
        const targetId = item.getAttribute('data-target');
        const targetSection = document.getElementById(targetId);
        
        if (!targetSection) return;

        // Auto-close sidebar on mobile
        const sidebar = document.getElementById('sidebar');
        if (window.innerWidth <= 768 && sidebar && sidebar.classList.contains('active')) {
            toggleSidebar();
        }

        // Switch active states
        document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
        item.classList.add('active');

        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
            section.classList.remove('slide-up');
        });

        targetSection.classList.add('active');
        setTimeout(() => targetSection.classList.add('slide-up'), 10);

        if (pageTitle) {
            pageTitle.innerText = item.innerText.trim();
        }

        // Trigger data loading
        if (targetId === 'view-admin-inventory') loadAdminInventory();
        if (targetId === 'view-admin-transactions') loadAdminTransactions();
        if (targetId === 'view-admin-requests') loadAdminRequests();
        if (targetId === 'view-issued-books') loadMyTransactions();
        if (targetId === 'view-catalog') loadCatalog('catalog-book-grid');
        if (targetId === 'view-overview') loadDashboardStats();
        if (targetId === 'view-fines') loadFineDetails();

        // Camera lifecycle
        if (targetId === 'view-kiosk') startKioskCamera();
        else stopKioskCamera();
    });
    const themeToggle = document.getElementById('themeToggle');
    const body = document.body;

    if (localStorage.getItem('theme') === 'dark') {
        body.setAttribute('data-theme', 'dark');
        if(themeToggle) themeToggle.innerHTML = '<i class="fa-solid fa-sun"></i>';
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            if (body.getAttribute('data-theme') === 'dark') {
                body.removeAttribute('data-theme');
                localStorage.setItem('theme', 'light');
                themeToggle.innerHTML = '<i class="fa-solid fa-moon"></i>';
            } else {
                body.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
                themeToggle.innerHTML = '<i class="fa-solid fa-sun"></i>';
            }
        });
    }

    // --- 6. LOGOUT LOGIC ---
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_role');
            localStorage.removeItem('user_name');
            showToast("Logged out successfully.", "success");
            setTimeout(() => window.location.href = 'index.html', 500);
        });
    }

    // --- 7. DASHBOARD DATA LOADING ---
    // Only run on the dashboard page
    if (document.getElementById('stat-issued')) {
        initDashboard();
    }

});

// ============================================================
// PHASE 2: Dynamic Data Functions
// ============================================================

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// --- Set user identity in header ---
function setUserIdentity(data) {
    const displayName = document.getElementById('user-display-name');
    const profileName = document.getElementById('user-profile-name');
    const avatar = document.getElementById('user-avatar');

    const name = capitalize(data.user_name);
    const role = capitalize(data.user_role);

    if (displayName) displayName.textContent = name;
    if (profileName) profileName.textContent = `${name} (${role})`;
    if (avatar) avatar.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=2563EB&color=fff`;
}

// --- Load dashboard stats ---
async function loadDashboardStats() {
    try {
        const data = await apiFetch('/api/dashboard/stats');
        if (!data) return;

        document.getElementById('stat-issued').textContent = data.books_issued;
        document.getElementById('stat-overdue').textContent = data.overdue_count;
        document.getElementById('stat-fines').textContent = `₹${data.total_fines.toFixed(2)}`;

        setUserIdentity(data);
    } catch (err) {
        console.error('Failed to load dashboard stats:', err);
        showToast("Could not load dashboard stats.", "error");
    }
}

// --- Render a single book card ---
function createBookCard(book) {
    const card = document.createElement('div');
    card.className = 'book-card';

    const icon = book.format === 'digital' ? 'fa-laptop-code' : 'fa-book';

    let badgeClass = '';
    let badgeText = capitalize(book.status);
    let badgeStyle = '';

    if (book.status === 'issued' || book.status === 'reserved') {
        badgeClass = 'issued';
    } else if (book.status === 'available') {
        badgeClass = '';
    }

    if (book.format === 'digital' && book.status === 'available') {
        badgeStyle = 'background: var(--primary); color: white;';
        badgeText = 'E-Book';
    }

    const issueBtn = (book.status === 'available' && book.format !== 'digital')
        ? `<button class="btn-sm btn-primary" style="margin-top:10px;" onclick="issueBook('${book.isbn}')">Issue Book</button>`
        : (book.format === 'digital' && book.status === 'available')
            ? `<button class="btn-sm btn-primary" style="margin-top:10px;" onclick="issueBook('${book.isbn}')">Borrow E-Book</button>`
            : '';

    card.innerHTML = `
        <div class="book-cover"><i class="fa-solid ${icon} fa-3x"></i></div>
        <div class="book-title">${book.title}</div>
        <div class="book-author">${book.category}</div>
        <span class="badge ${badgeClass}" ${badgeStyle ? `style="${badgeStyle}"` : ''}>${badgeText}</span>
        ${issueBtn}
    `;
    return card;
}

// --- Global catalog cache for client-side filtering ---
let allCatalogBooks = [];

// --- Render books into a grid (no fetch, just DOM) ---
function renderCatalogGrid(books, targetGridId) {
    const grid = document.getElementById(targetGridId);
    if (!grid) return;
    grid.innerHTML = '';

    if (books.length === 0) {
        grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-muted);"><i class="fa-solid fa-book-open" style="font-size:2rem;margin-bottom:12px;"></i><p>No books match your search.</p></div>';
        return;
    }
    books.forEach(book => grid.appendChild(createBookCard(book)));
}

// --- Load catalog into a grid ---
async function loadCatalog(targetGridId = 'catalog-book-grid') {
    const grid = document.getElementById(targetGridId);
    if (!grid) return;

    try {
        const books = await apiFetch('/api/books');
        if (!books) return;

        // Cache the full catalog for the main catalog grid
        if (targetGridId === 'catalog-book-grid') {
            allCatalogBooks = books;
        }

        renderCatalogGrid(books, targetGridId);
    } catch (err) {
        console.error('Failed to load catalog:', err);
        grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--danger);"><i class="fa-solid fa-triangle-exclamation fa-2x"></i><p style="margin-top:12px;">Failed to load catalog. Is the server running?</p></div>';
    }
}

// --- Load Admin Approval Requests ---
async function loadAdminRequests() {
    console.log("Fetching pending requests from API...");
    const tbody = document.getElementById('admin-requests-body');
    if (!tbody) {
        console.error("Target tbody 'admin-requests-body' not found!");
        return;
    }

    try {
        const requests = await apiFetch('/api/admin/requests');
        console.log("Requests received:", requests);
        tbody.innerHTML = '';

        if (!requests || requests.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px;">No pending requests.</td></tr>';
            return;
        }

        requests.forEach(req => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${req.user_name}</td>
                <td>${req.book_title}</td>
                <td>${new Date(req.date).toLocaleDateString()}</td>
                <td><span class="badge ${req.status}">${capitalize(req.status.replace('_', ' '))}</span></td>
                <td>
                    <button class="btn-sm btn-primary admin-approve-btn" data-id="${req.transaction_id}">Approve</button>
                    <button class="btn-sm btn-outline admin-reject-btn" data-id="${req.transaction_id}">Reject</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (err) {
        console.error('Failed to load admin requests:', err);
    }
}

// Global listener for Admin Requests (Event Delegation)
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('admin-approve-btn')) {
        const txnId = e.target.getAttribute('data-id');
        processRequest(txnId, 'approve');
    }
    if (e.target.classList.contains('admin-reject-btn')) {
        const txnId = e.target.getAttribute('data-id');
        processRequest(txnId, 'reject');
    }
});

// --- Process (Approve/Reject) Request ---
async function processRequest(txnId, action) {
    try {
        console.log(`Sending POST request for TXN: ${txnId}, Action: ${action}`);
        const data = await apiFetch(`/api/admin/approve/${txnId}?action=${action}`, { 
            method: 'POST' 
        });
        showToast(data.message, 'success');
        
        // Refresh EVERYTHING to ensure catalog sync
        loadAdminRequests(); 
        loadAdminInventory();
        loadCatalog('catalog-book-grid'); 
        loadAdminTransactions();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// --- Load user's transactions into the table ---
async function loadMyTransactions() {
    const tbody = document.getElementById('issued-table-body');
    if (!tbody) return;

    try {
        const transactions = await apiFetch('/api/transactions/me');
        if (!transactions) return;

        tbody.innerHTML = ''; // Clear loading spinner

        if (transactions.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:40px; color:var(--text-muted);">
                <i class="fa-solid fa-check-circle fa-2x" style="color:var(--primary);"></i>
                <p style="margin-top:12px;">You have no active or overdue books. 🎉</p>
            </td></tr>`;
            return;
        }

        transactions.forEach(txn => {
            const row = document.createElement('tr');
            
            // Handle statuses
            let badgeClass = '';
            let statusLabel = capitalize(txn.status);
            let actionBtn = '';

            if (txn.status === 'overdue') {
                badgeClass = 'issued'; // Red badge
                actionBtn = `<button class="btn-sm btn-primary" onclick="returnBook('${txn.isbn}')" style="background:var(--danger);">Return (Overdue)</button>`;
            } else if (txn.status === 'active') {
                actionBtn = `<button class="btn-sm btn-primary" onclick="returnBook('${txn.isbn}')">Return</button>`;
            } else if (txn.status === 'pending_return') {
                statusLabel = 'Pending Return';
                badgeClass = 'reserved'; // Yellow-ish
                actionBtn = `<span class="text-muted">Awaiting Return Approval</span>`;
            } else if (txn.status === 'pending_issue') {
                statusLabel = 'Pending Issue';
                badgeClass = 'reserved';
                actionBtn = `<span class="text-muted">Awaiting Issue Approval</span>`;
            }

            row.innerHTML = `
                <td><strong>${txn.book_title}</strong><br><small class="text-muted">${txn.isbn}</small></td>
                <td>${txn.issue_date}</td>
                <td>${txn.due_date}</td>
                <td><span class="badge ${badgeClass}">${statusLabel}</span></td>
                <td>${actionBtn}</td>
            `;
            tbody.appendChild(row);
        });
    } catch (err) {
        console.error('Failed to load transactions:', err);
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:40px; color:var(--danger);">
            <i class="fa-solid fa-triangle-exclamation fa-2x"></i>
            <p style="margin-top:12px;">Failed to load issued books.</p>
        </td></tr>`;
    }
}

// --- Issue a book (Phase 3) ---
async function issueBook(isbn) {
    try {
        const data = await apiFetch(`/api/transactions/issue/${isbn}`, { method: 'POST' });
        if (!data) return;
        showToast(data.message || 'Book issued successfully!', 'success');

        // Refresh everything: catalog, transactions, AND dashboard stats
        await Promise.all([
            loadCatalog('catalog-book-grid'),
            loadCatalog('dashboard-book-grid'),
            loadMyTransactions(),
            loadDashboardStats() 
        ]);
    } catch (err) {
        showToast(err.message || 'Failed to issue book.', 'error');
    }
}

// --- Return a book (Phase 3) ---
async function returnBook(isbn) {
    try {
        const data = await apiFetch(`/api/transactions/return/${isbn}`, { method: 'POST' });
        if (!data) return;
        showToast(data.message || 'Book returned successfully!', 'success');

        // Refresh issued-books table and catalog grids in real time
        await Promise.all([
            loadMyTransactions(),
            loadCatalog('catalog-book-grid'),
            loadCatalog('dashboard-book-grid'),
            loadDashboardStats(),
        ]);
    } catch (err) {
        showToast(err.message || 'Failed to return book.', 'error');
    }
}

// --- Catalog Search & Filter (Phase 3) ---
function filterCatalog() {
    const searchInput = document.getElementById('catalog-search');
    const categorySelect = document.getElementById('catalog-category-filter');
    const formatSelect = document.getElementById('catalog-format-filter');

    const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
    const category = categorySelect ? categorySelect.value : '';
    const formatFilter = formatSelect ? formatSelect.value : '';

    let filtered = allCatalogBooks;

    // Text search: match title, category, or ISBN
    if (query) {
        filtered = filtered.filter(book =>
            book.title.toLowerCase().includes(query) ||
            (book.category || '').toLowerCase().includes(query) ||
            book.isbn.toLowerCase().includes(query)
        );
    }

    // Category filter
    if (category) {
        filtered = filtered.filter(book => book.category === category);
    }

    // Format/status filter
    if (formatFilter === 'available') {
        filtered = filtered.filter(book => book.status === 'available');
    } else if (formatFilter === 'digital') {
        filtered = filtered.filter(book => book.format === 'digital');
    }

    renderCatalogGrid(filtered, 'catalog-book-grid');
}

// --- Attach search & filter listeners ---
function initCatalogFilters() {
    const searchInput = document.getElementById('catalog-search');
    const categorySelect = document.getElementById('catalog-category-filter');
    const formatSelect = document.getElementById('catalog-format-filter');

    if (searchInput) {
        // Correctly replace listeners to avoid ghosting
        const newSearchInput = searchInput.cloneNode(true);
        searchInput.parentNode.replaceChild(newSearchInput, searchInput);
        newSearchInput.addEventListener('input', filterCatalog);
    }
    if (categorySelect) {
        const newCatSelect = categorySelect.cloneNode(true);
        categorySelect.parentNode.replaceChild(newCatSelect, categorySelect);
        newCatSelect.addEventListener('change', filterCatalog);
    }
    if (formatSelect) {
        const newFormatSelect = formatSelect.cloneNode(true);
        formatSelect.parentNode.replaceChild(newFormatSelect, formatSelect);
        newFormatSelect.addEventListener('change', filterCatalog);
    }
}

// ============================================================
// PHASE 4: AI Academic Assistant Chat Widget
// ============================================================

// --- Simple markdown-to-HTML for bot responses ---
function markdownToHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/\n- /g, '\n• ')
        .replace(/\n(\d+)\. /g, '\n$1. ')
        .replace(/\n/g, '<br>');
}

// --- Append a chat bubble ---
function appendChatBubble(text, type = 'bot') {
    const messages = document.getElementById('chatMessages');
    if (!messages) return;

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${type}-bubble`;

    if (type === 'bot') {
        bubble.innerHTML = markdownToHtml(text);
    } else {
        bubble.textContent = text;
    }

    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
}

// --- Show / hide typing indicator ---
function showTypingIndicator() {
    const messages = document.getElementById('chatMessages');
    if (!messages) return null;

    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.id = 'typing-indicator';
    indicator.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
    messages.appendChild(indicator);
    messages.scrollTop = messages.scrollHeight;
    return indicator;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
}

// --- Send a message to the AI ---
async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    if (!input) return;

    const text = input.value.trim();
    if (!text) return;

    // Append user bubble
    appendChatBubble(text, 'user');
    input.value = '';

    // Show typing indicator
    showTypingIndicator();

    try {
        const data = await apiFetch('/api/chat', {
            method: 'POST',
            body: JSON.stringify({ message: text }),
        });
        removeTypingIndicator();
        if (data && data.reply) {
            appendChatBubble(data.reply, 'bot');
        } else {
            appendChatBubble('Sorry, I couldn\'t process that. Please try again.', 'bot');
        }
    } catch (err) {
        removeTypingIndicator();
        appendChatBubble('⚠️ Connection error. Please ensure the server is running.', 'bot');
    }
}

// --- Toggle chat window ---
function toggleChatWindow() {
    const chatWindow = document.getElementById('chatWindow');
    const fab = document.getElementById('chatToggleBtn');
    if (!chatWindow || !fab) return;

    const isOpen = chatWindow.classList.contains('open');
    if (isOpen) {
        chatWindow.style.opacity = '0';
        chatWindow.style.transform = 'translateY(20px) scale(0.95)';
        setTimeout(() => {
            chatWindow.classList.remove('open');
            chatWindow.style.display = 'none';
        }, 200);
        fab.classList.remove('active');
    } else {
        chatWindow.style.display = 'flex';
        // Force reflow before adding open class for animation
        chatWindow.offsetHeight;
        chatWindow.classList.add('open');
        chatWindow.style.opacity = '1';
        chatWindow.style.transform = 'translateY(0) scale(1)';
        fab.classList.add('active');

        // Focus input
        const input = document.getElementById('chatInput');
        if (input) input.focus();
    }
}

// --- Initialize chat event listeners ---
function initChat() {
    const fab = document.getElementById('chatToggleBtn');
    const closeBtn = document.getElementById('chatCloseBtn');
    const sendBtn = document.getElementById('chatSendBtn');
    const input = document.getElementById('chatInput');

    if (fab) fab.addEventListener('click', toggleChatWindow);
    if (closeBtn) closeBtn.addEventListener('click', toggleChatWindow);
    if (sendBtn) sendBtn.addEventListener('click', sendChatMessage);
    if (input) {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }
}

// --- Initialize the dashboard: load all dynamic data ---
async function initDashboard() {
    // Check authentication
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = 'index.html';
        return;
    }

    // Fire all data loads concurrently
    await Promise.all([
        loadDashboardStats(),
        loadCatalog('dashboard-book-grid'),  // "Recommended for You" grid
        loadCatalog('catalog-book-grid'),    // Main catalog (also caches for filtering)
        loadMyTransactions(),
    ]);

    // Wire up search & filter after data is loaded
    initCatalogFilters();

    // Initialize the AI chat widget
    initChat();

    // Initialize the Smart Return Kiosk
    initKiosk();
}

// --- GLOBAL TOAST FUNCTION ---
function showToast(message, type = "success") {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icon = type === 'success' ? '<i class="fa-solid fa-circle-check"></i>' : '<i class="fa-solid fa-circle-exclamation"></i>';
    toast.innerHTML = `${icon} <span>${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==========================================
// --- SMART RETURN KIOSK LOGIC (Phase 4.2) ---
// ==========================================

let kioskStream = null;
let isScanning = false;

function initKiosk() {
    const scanBtn = document.getElementById('kiosk-scan-btn');
    const manualBtn = document.getElementById('kiosk-manual-btn');
    const manualInput = document.getElementById('kiosk-manual-isbn');

    if (scanBtn) {
        scanBtn.addEventListener('click', captureAndScan);
    }

    if (manualBtn) {
        manualBtn.addEventListener('click', () => {
            const isbn = manualInput.value.trim();
            if (isbn) {
                returnBook(isbn); // Reusing existing Phase 3 logic
                manualInput.value = '';
            } else {
                showToast('Please enter an ISBN first', 'error');
            }
        });
    }
}

async function startKioskCamera() {
    const video = document.getElementById('kiosk-video');
    const placeholder = document.getElementById('kiosk-placeholder');

    try {
        kioskStream = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'environment' }, 
            audio: false 
        });
        video.srcObject = kioskStream;
        placeholder.classList.add('hidden');
        showToast('Camera activated', 'success');
    } catch (err) {
        console.error("Camera Error:", err);
        showToast('Could not access camera. Use manual override.', 'error');
    }
}

function stopKioskCamera() {
    if (kioskStream) {
        kioskStream.getTracks().forEach(track => track.stop());
        kioskStream = null;
    }
    const video = document.getElementById('kiosk-video');
    const placeholder = document.getElementById('kiosk-placeholder');
    if (video) video.srcObject = null;
    if (placeholder) placeholder.classList.remove('hidden');
}

async function captureAndScan() {
    if (isScanning) return;
    
    const video = document.getElementById('kiosk-video');
    const canvas = document.getElementById('kiosk-canvas');
    const statusDiv = document.getElementById('kiosk-status');
    const overlay = document.getElementById('kiosk-scan-overlay');
    const rawTextDiv = document.getElementById('kiosk-extracted-text');
    const rawTextPre = document.getElementById('kiosk-raw-text');

    if (!kioskStream) {
        showToast('Camera is not active', 'error');
        return;
    }

    isScanning = true;
    overlay.classList.add('scanning');
    statusDiv.innerHTML = `
        <div class="kiosk-status-idle">
            <i class="fa-solid fa-spinner fa-spin fa-2x"></i>
            <p><strong>Analyzing Book Cover...</strong><br>Using Tesseract OCR Engine</p>
        </div>
    `;

    try {
        // 1. Capture frame to canvas
        const context = canvas.getContext('2d');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        // 2. Run Tesseract OCR
        const result = await Tesseract.recognize(canvas, 'eng', {
            logger: m => console.log(m)
        });

        const text = result.data.text;
        console.log("OCR Result:", text);

        // 3. Regex for ISBN (ISBN-10 or ISBN-13)
        // Looks for 978... or 979... or standard 10 digit patterns
        const isbnRegex = /(?:ISBN(?:-1[03])?:?\s*)?((?=[0-9X]{10}|(?=(?:[0-9]+[- ]){3})[0-9X -]{13}|97[89][0-9]{10}|(?=(?:[0-9]+[- ]){4})[0-9X -]{17})(?:97[89][- ]?)?[0-9]{1,5}[- ]?[0-9]+[- ]?[0-9]+[- ]?[0-9X])/i;
        const match = text.match(isbnRegex);

        // Show raw text for debugging/demo
        rawTextDiv.style.display = 'block';
        rawTextPre.innerText = text || "No text detected";

        if (match && match[0]) {
            let cleanIsbn = match[0].replace(/ISBN/i, '').replace(/[:\s-]/g, '').trim();
            
            statusDiv.innerHTML = `
                <div class="kiosk-status-idle">
                    <i class="fa-solid fa-circle-check fa-2x"></i>
                    <p style="color:#10B981"><strong>Success! Detected ISBN: ${cleanIsbn}</strong><br>Processing return...</p>
                </div>
            `;
            
            // Trigger existing return logic
            await returnBook(cleanIsbn);
        } else {
            statusDiv.innerHTML = `
                <div class="kiosk-status-idle">
                    <i class="fa-solid fa-triangle-exclamation fa-2x"></i>
                    <p style="color:var(--danger)"><strong>Could not detect ISBN</strong><br>Try a clearer angle or use manual override.</p>
                </div>
            `;
            showToast('OCR failed to find ISBN', 'error');
        }

    } catch (err) {
        console.error("Scan Error:", err);
        showToast('OCR Engine Error', 'error');
    } finally {
        isScanning = false;
        overlay.classList.remove('scanning');
    }
}

// ==========================================
// --- ADMIN DASHBOARD MODULE (Phase 5) ---
// ==========================================

function initAdminRole() {
    const role = localStorage.getItem('user_role');
    const adminLinks = document.querySelectorAll('.admin-only');
    
    if (role === 'admin') {
        adminLinks.forEach(el => el.style.display = 'block');
        initForecaster();
    }
}

// 1. Demand Forecaster Logic
function initForecaster() {
    const forecasterCard = document.getElementById('admin-forecaster-card');
    const msg = document.getElementById('forecaster-msg');
    if (!forecasterCard) return;

    const currentMonth = new Date().getMonth(); // 0-11
    // Exam seasons: May (4) and November (10)
    if (currentMonth === 4 || currentMonth === 3 || currentMonth === 10 || currentMonth === 9) {
        msg.innerHTML = `<strong>Predictive Alert:</strong> Midterms approaching. High demand expected for 'Computer Science' and 'Mathematics'. Consider recalling overdue copies.`;
        forecasterCard.style.display = 'block';
    } else {
        msg.innerText = "Library demand is currently stable. No predictive alerts.";
        forecasterCard.style.display = 'block';
    }
}

// 2. Inventory Management
async function loadAdminInventory() {
    const tableBody = document.getElementById('admin-inventory-table');
    if (!tableBody) return;

    tableBody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:40px;"><i class="fa-solid fa-spinner fa-spin fa-2x"></i></td></tr>`;

    try {
        const books = await apiFetch('/api/books'); 
        tableBody.innerHTML = '';
        books.forEach(book => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><code>${book.isbn}</code></td>
                <td><strong>${book.title}</strong></td>
                <td>${book.category}</td>
                <td><span class="badge" style="background:#f1f5f9; color:#475569">${book.format}</span></td>
                <td><span class="badge ${book.status}">${book.status}</span></td>
                <td>
                    <button class="btn-sm" style="color:var(--danger); border-color:rgba(239,68,68,0.2)" onclick="deleteBook('${book.isbn}')">
                        <i class="fa-solid fa-trash-can"></i> Delete
                    </button>
                </td>
            `;
            tableBody.appendChild(row);
        });
    } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="6" style="color:var(--danger); text-align:center;">Failed to load inventory.</td></tr>`;
    }
}

async function deleteBook(isbn) {
    if (!confirm(`Are you sure you want to delete book ISBN: ${isbn}?`)) return;

    try {
        await apiFetch(`/api/admin/books/${isbn}`, { method: 'DELETE' });
        showToast("Book deleted successfully", "success");
        loadAdminInventory();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// 3. Global Transactions
async function loadAdminTransactions() {
    const tableBody = document.getElementById('admin-transactions-table');
    if (!tableBody) return;

    tableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:40px;"><i class="fa-solid fa-spinner fa-spin fa-2x"></i></td></tr>`;

    try {
        const transactions = await apiFetch('/api/admin/transactions');
        tableBody.innerHTML = '';
        if (transactions.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No transaction history found.</td></tr>`;
            return;
        }
        transactions.forEach(tx => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${tx.user_name}</strong></td>
                <td>${tx.book_title}</td>
                <td>${tx.issue_date}</td>
                <td>${tx.due_date}</td>
                <td><span class="badge ${tx.status}">${tx.status}</span></td>
            `;
            tableBody.appendChild(row);
        });
    } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="5" style="color:var(--danger); text-align:center;">Failed to load transactions.</td></tr>`;
    }
}

// 4. Add Book Modal Functions
function openAddBookModal() {
    document.getElementById('addBookModal').style.display = 'flex';
}

function closeAddBookModal() {
    document.getElementById('addBookModal').style.display = 'none';
}

// Setup Modal Form Listener
document.addEventListener('DOMContentLoaded', () => {
    const addBookForm = document.getElementById('addBookForm');
    if (addBookForm) {
        addBookForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const bookData = {
                isbn: document.getElementById('add-isbn').value,
                title: document.getElementById('add-title').value,
                category: document.getElementById('add-category').value,
                format: document.getElementById('add-format').value
            };

            try {
                await apiFetch('/api/admin/books', {
                    method: 'POST',
                    body: JSON.stringify(bookData)
                });
                showToast("Book added to library!", "success");
                closeAddBookModal();
                addBookForm.reset();
                if (document.getElementById('view-admin-inventory').classList.contains('active')) {
                    loadAdminInventory();
                }
            } catch (err) {
                showToast(err.message, "error");
            }
        });
    }
    
    // Auto-init admin role on load
    initAdminRole();
});

// Fine Payment Functions
async function loadFineDetails() {
    try {
        const stats = await apiFetch('/api/dashboard/stats');
        const amountDisplay = document.getElementById('fine-amount-display');
        if (amountDisplay) amountDisplay.innerText = `₹${stats.total_fines.toFixed(2)}`;

        const tbody = document.getElementById('fines-table-body');
        if (!tbody) return;

        const txns = await apiFetch('/api/transactions/me');
        const overdue = txns.filter(t => t.status === 'overdue');

        tbody.innerHTML = '';
        if (overdue.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px;">No overdue books. You are all caught up!</td></tr>';
            return;
        }

        overdue.forEach(t => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${t.book_title}</strong></td>
                <td>${t.isbn}</td>
                <td>${new Date(t.due_date).toLocaleDateString()}</td>
                <td><span class="badge issued">OVERDUE</span></td>
                <td>₹50.00</td>
            `;
            tbody.appendChild(row);
        });
    } catch (err) { console.error(err); }
}

async function payFine() {
    try {
        const data = await apiFetch('/api/fines/pay', { method: 'POST' });
        showToast(data.message, 'success');
        loadFineDetails();
        loadDashboardStats();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Global listener for dynamic buttons
document.addEventListener('click', function(e) {
    if (e.target.id === 'btn-pay-fine') {
        payFine();
    }
});