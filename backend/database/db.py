import os
import json
import sqlite3
import uuid
from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from passlib.context import CryptContext
from backend.config import settings

import bcrypt

def get_db_connection():
    os.makedirs(os.path.dirname(settings.SQLITE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(settings.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    # bcrypt requires <= 72 bytes
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        role TEXT DEFAULT 'USER',
        avatar_url TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # Items Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        brand TEXT,
        color TEXT,
        distinguishing_features TEXT,
        image_url TEXT,
        location TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        event_date TEXT NOT NULL,
        event_time TEXT NOT NULL,
        status TEXT DEFAULT 'ACTIVE',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Item Embeddings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS item_embeddings (
        id TEXT PRIMARY KEY,
        item_id TEXT UNIQUE NOT NULL,
        image_embedding TEXT,
        text_embedding TEXT,
        model_name TEXT DEFAULT 'all-MiniLM-L6-v2',
        created_at TEXT NOT NULL,
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE
    )
    """)

    # Matches Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id TEXT PRIMARY KEY,
        lost_item_id TEXT NOT NULL,
        found_item_id TEXT NOT NULL,
        image_similarity REAL DEFAULT 0.0,
        text_similarity REAL DEFAULT 0.0,
        category_similarity REAL DEFAULT 0.0,
        brand_similarity REAL DEFAULT 0.0,
        color_similarity REAL DEFAULT 0.0,
        location_similarity REAL DEFAULT 0.0,
        time_similarity REAL DEFAULT 0.0,
        final_confidence REAL NOT NULL,
        status TEXT DEFAULT 'POTENTIAL_MATCH',
        created_at TEXT NOT NULL,
        UNIQUE(lost_item_id, found_item_id),
        FOREIGN KEY (lost_item_id) REFERENCES items (id) ON DELETE CASCADE,
        FOREIGN KEY (found_item_id) REFERENCES items (id) ON DELETE CASCADE
    )
    """)

    # Claims Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        id TEXT PRIMARY KEY,
        match_id TEXT,
        item_id TEXT NOT NULL,
        claimant_id TEXT NOT NULL,
        verification_answers TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        reviewed_by TEXT,
        review_notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE,
        FOREIGN KEY (claimant_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Gamification Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gamification (
        user_id TEXT PRIMARY KEY,
        current_streak INTEGER DEFAULT 0,
        longest_streak INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,
        verified_reports INTEGER DEFAULT 0,
        successful_returns INTEGER DEFAULT 0,
        last_activity TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Badges Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS badges (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        icon TEXT NOT NULL
    )
    """)

    # User Badges Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_badges (
        user_id TEXT NOT NULL,
        badge_id TEXT NOT NULL,
        earned_at TEXT NOT NULL,
        PRIMARY KEY (user_id, badge_id),
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (badge_id) REFERENCES badges (id) ON DELETE CASCADE
    )
    """)

    # Notifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    conn.commit()

    # Seed Default Badges
    default_badges = [
        ("first_finder", "First Finder", "Reported your first verified found item.", "award"),
        ("community_helper", "Community Helper", "Successfully helped reconnect a lost belonging with its owner.", "shield-check"),
        ("streak_7", "7-Day Helper", "Maintained an active 7-day verified activity streak.", "zap"),
        ("streak_30", "30-Day Helper", "Maintained a dedicated 30-day verified helper streak.", "sparkles"),
        ("recovery_hero", "Recovery Hero", "Facilitated 3 or more successful campus recoveries.", "heart-handshake")
    ]
    for badge in default_badges:
        cursor.execute("INSERT OR IGNORE INTO badges (id, name, description, icon) VALUES (?, ?, ?, ?)", badge)

    # Seed Default Users if none exist
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    if user_count == 0:
        now_str = datetime.now().isoformat()
        admin_id = str(uuid.uuid4())
        student_a_id = str(uuid.uuid4())
        student_b_id = str(uuid.uuid4())

        cursor.execute("""
        INSERT INTO users (id, name, email, hashed_password, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (admin_id, "Campus Security Admin", "admin@campus.edu", hash_password("AdminPass123!"), "ADMIN", now_str))

        cursor.execute("""
        INSERT INTO users (id, name, email, hashed_password, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (student_a_id, "Alex Rivera", "alex@campus.edu", hash_password("StudentPass123!"), "USER", now_str))

        cursor.execute("""
        INSERT INTO users (id, name, email, hashed_password, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (student_b_id, "Sarah Chen", "sarah@campus.edu", hash_password("StudentPass123!"), "USER", now_str))

        # Seed gamification records
        cursor.execute("INSERT INTO gamification (user_id, current_streak, longest_streak, points, verified_reports, successful_returns, last_activity) VALUES (?, 0, 0, 0, 0, 0, NULL)", (admin_id,))
        cursor.execute("INSERT INTO gamification (user_id, current_streak, longest_streak, points, verified_reports, successful_returns, last_activity) VALUES (?, 2, 5, 40, 2, 0, ?)", (student_a_id, date.today().isoformat()))
        cursor.execute("INSERT INTO gamification (user_id, current_streak, longest_streak, points, verified_reports, successful_returns, last_activity) VALUES (?, 7, 7, 180, 8, 3, ?)", (student_b_id, date.today().isoformat()))

        # Give Sarah Chen the First Finder and Community Helper badges
        cursor.execute("INSERT INTO user_badges (user_id, badge_id, earned_at) VALUES (?, ?, ?)", (student_b_id, "first_finder", now_str))
        cursor.execute("INSERT INTO user_badges (user_id, badge_id, earned_at) VALUES (?, ?, ?)", (student_b_id, "community_helper", now_str))
        cursor.execute("INSERT INTO user_badges (user_id, badge_id, earned_at) VALUES (?, ?, ?)", (student_b_id, "streak_7", now_str))

    conn.commit()
    conn.close()

# User Operations
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(name: str, email: str, password_hash: str, role: str = "USER") -> Dict[str, Any]:
    user_id = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO users (id, name, email, hashed_password, role, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, name, email.strip().lower(), password_hash, role, now_str))
    
    # Initialize gamification profile
    cursor.execute("""
    INSERT INTO gamification (user_id, current_streak, longest_streak, points, verified_reports, successful_returns)
    VALUES (?, 0, 0, 0, 0, 0)
    """, (user_id,))
    
    conn.commit()
    conn.close()
    return {"id": user_id, "name": name, "email": email.strip().lower(), "role": role, "created_at": now_str}

# Item Operations
def create_item(item_data: Dict[str, Any]) -> Dict[str, Any]:
    item_id = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO items (
        id, user_id, type, title, category, description, brand, color,
        distinguishing_features, image_url, location, latitude, longitude,
        event_date, event_time, status, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item_id, item_data["user_id"], item_data["type"], item_data["title"],
        item_data["category"], item_data["description"], item_data.get("brand", ""),
        item_data.get("color", ""), item_data.get("distinguishing_features", ""),
        item_data.get("image_url"), item_data["location"], item_data.get("latitude"),
        item_data.get("longitude"), item_data["event_date"], item_data["event_time"],
        item_data.get("status", "ACTIVE"), now_str, now_str
    ))
    conn.commit()
    conn.close()
    return get_item_by_id(item_id)

def get_item_by_id(item_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT i.*, u.name as user_name
    FROM items i
    LEFT JOIN users u ON i.user_id = u.id
    WHERE i.id = ?
    """, (item_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_items(
    item_type: Optional[str] = None,
    category: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    search_query: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT i.*, u.name as user_name
    FROM items i
    LEFT JOIN users u ON i.user_id = u.id
    WHERE 1=1
    """
    params = []

    if item_type:
        query += " AND i.type = ?"
        params.append(item_type)
    if category:
        query += " AND LOWER(i.category) = LOWER(?)"
        params.append(category)
    if location:
        query += " AND LOWER(i.location) = LOWER(?)"
        params.append(location)
    if status:
        query += " AND i.status = ?"
        params.append(status)
    if user_id:
        query += " AND i.user_id = ?"
        params.append(user_id)
    if search_query:
        query += " AND (LOWER(i.title) LIKE ? OR LOWER(i.description) LIKE ? OR LOWER(i.brand) LIKE ?)"
        term = f"%{search_query.lower()}%"
        params.extend([term, term, term])

    query += " ORDER BY i.created_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_item(item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    updates["updated_at"] = now_str
    
    set_clauses = [f"{k} = ?" for k in updates.keys()]
    values = list(updates.values())
    values.append(item_id)
    
    cursor.execute(f"UPDATE items SET {', '.join(set_clauses)} WHERE id = ?", tuple(values))
    conn.commit()
    conn.close()
    return get_item_by_id(item_id)

def delete_item(item_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return True

# Embeddings Operations
def save_item_embeddings(item_id: str, image_embedding: Optional[List[float]], text_embedding: Optional[List[float]], model_name: str = "all-MiniLM-L6-v2"):
    conn = get_db_connection()
    cursor = conn.cursor()
    emb_id = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    img_json = json.dumps(image_embedding) if image_embedding is not None else None
    txt_json = json.dumps(text_embedding) if text_embedding is not None else None

    cursor.execute("""
    INSERT INTO item_embeddings (id, item_id, image_embedding, text_embedding, model_name, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(item_id) DO UPDATE SET
        image_embedding = excluded.image_embedding,
        text_embedding = excluded.text_embedding,
        model_name = excluded.model_name
    """, (emb_id, item_id, img_json, txt_json, model_name, now_str))
    conn.commit()
    conn.close()

def get_item_embeddings(item_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM item_embeddings WHERE item_id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["image_embedding"] = json.loads(d["image_embedding"]) if d["image_embedding"] else None
    d["text_embedding"] = json.loads(d["text_embedding"]) if d["text_embedding"] else None
    return d

def get_all_embeddings_by_type(target_type: str) -> List[Dict[str, Any]]:
    """Returns all items of a specific type (e.g. 'found' or 'lost') with their embeddings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT i.*, e.image_embedding, e.text_embedding, e.model_name, u.name as user_name
    FROM items i
    LEFT JOIN item_embeddings e ON i.id = e.item_id
    LEFT JOIN users u ON i.user_id = u.id
    WHERE i.type = ? AND i.status IN ('ACTIVE', 'MATCH_FOUND', 'CLAIM_PENDING')
    """, (target_type,))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["image_embedding"] = json.loads(d["image_embedding"]) if d["image_embedding"] else None
        d["text_embedding"] = json.loads(d["text_embedding"]) if d["text_embedding"] else None
        result.append(d)
    return result

# Matches Operations
def save_match(match_data: Dict[str, Any]) -> str:
    match_id = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO matches (
        id, lost_item_id, found_item_id, image_similarity, text_similarity,
        category_similarity, brand_similarity, color_similarity,
        location_similarity, time_similarity, final_confidence, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(lost_item_id, found_item_id) DO UPDATE SET
        image_similarity = excluded.image_similarity,
        text_similarity = excluded.text_similarity,
        category_similarity = excluded.category_similarity,
        brand_similarity = excluded.brand_similarity,
        color_similarity = excluded.color_similarity,
        location_similarity = excluded.location_similarity,
        time_similarity = excluded.time_similarity,
        final_confidence = excluded.final_confidence,
        status = excluded.status
    """, (
        match_id, match_data["lost_item_id"], match_data["found_item_id"],
        match_data.get("image_similarity", 0.0), match_data.get("text_similarity", 0.0),
        match_data.get("category_similarity", 0.0), match_data.get("brand_similarity", 0.0),
        match_data.get("color_similarity", 0.0), match_data.get("location_similarity", 0.0),
        match_data.get("time_similarity", 0.0), match_data["final_confidence"],
        match_data.get("status", "POTENTIAL_MATCH"), now_str
    ))
    conn.commit()
    conn.close()
    return match_id

def get_matches_for_item(item_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT m.*, 
           l.title as lost_title, l.category as lost_category, l.location as lost_location, l.image_url as lost_image,
           f.title as found_title, f.category as found_category, f.location as found_location, f.image_url as found_image,
           f.brand as found_brand, f.color as found_color, f.event_date as found_date, f.event_time as found_time,
           f.description as found_description, f.status as found_status, f.user_id as finder_id
    FROM matches m
    JOIN items l ON m.lost_item_id = l.id
    JOIN items f ON m.found_item_id = f.id
    WHERE m.lost_item_id = ? OR m.found_item_id = ?
    ORDER BY m.final_confidence DESC
    LIMIT ?
    """, (item_id, item_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Claims Operations
def create_claim(claim_data: Dict[str, Any]) -> Dict[str, Any]:
    claim_id = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    answers_json = json.dumps(claim_data["verification_answers"])
    cursor.execute("""
    INSERT INTO claims (
        id, match_id, item_id, claimant_id, verification_answers, status, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        claim_id, claim_data.get("match_id"), claim_data["item_id"],
        claim_data["claimant_id"], answers_json, "PENDING", now_str, now_str
    ))
    
    # Update item status to CLAIM_PENDING
    cursor.execute("UPDATE items SET status = 'CLAIM_PENDING' WHERE id = ?", (claim_data["item_id"],))
    conn.commit()
    conn.close()
    return get_claim_by_id(claim_id)

def get_claim_by_id(claim_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.*, i.title as item_title, i.type as item_type, i.image_url as item_image,
           u.name as claimant_name, u.email as claimant_email
    FROM claims c
    JOIN items i ON c.item_id = i.id
    JOIN users u ON c.claimant_id = u.id
    WHERE c.id = ?
    """, (claim_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["verification_answers"] = json.loads(d["verification_answers"])
    return d

def list_claims(status: Optional[str] = None, claimant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT c.*, i.title as item_title, i.type as item_type, i.image_url as item_image,
           u.name as claimant_name, u.email as claimant_email
    FROM claims c
    JOIN items i ON c.item_id = i.id
    JOIN users u ON c.claimant_id = u.id
    WHERE 1=1
    """
    params = []
    if status:
        query += " AND c.status = ?"
        params.append(status)
    if claimant_id:
        query += " AND c.claimant_id = ?"
        params.append(claimant_id)
    query += " ORDER BY c.created_at DESC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["verification_answers"] = json.loads(d["verification_answers"])
        results.append(d)
    return results

def update_claim_status(claim_id: str, new_status: str, reviewer_id: Optional[str] = None, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
    UPDATE claims
    SET status = ?, reviewed_by = ?, review_notes = ?, updated_at = ?
    WHERE id = ?
    """, (new_status, reviewer_id, notes, now_str, claim_id))
    
    # If claim is verified or returned, update corresponding item status
    cursor.execute("SELECT item_id FROM claims WHERE id = ?", (claim_id,))
    row = cursor.fetchone()
    if row:
        item_id = row[0]
        if new_status == "VERIFIED":
            cursor.execute("UPDATE items SET status = 'VERIFIED' WHERE id = ?", (item_id,))
        elif new_status == "RETURNED":
            cursor.execute("UPDATE items SET status = 'RETURNED' WHERE id = ?", (item_id,))
        elif new_status == "REJECTED":
            cursor.execute("UPDATE items SET status = 'ACTIVE' WHERE id = ?", (item_id,))

    conn.commit()
    conn.close()
    return get_claim_by_id(claim_id)

# Gamification Operations
def get_gamification_profile(user_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gamification WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO gamification (user_id) VALUES (?)", (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM gamification WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    
    profile = dict(row)
    
    # Fetch earned badges
    cursor.execute("""
    SELECT b.*, ub.earned_at
    FROM badges b
    JOIN user_badges ub ON b.id = ub.badge_id
    WHERE ub.user_id = ?
    """, (user_id,))
    earned_rows = cursor.fetchall()
    earned_dict = {r["id"]: dict(r) for r in earned_rows}

    # Fetch all badges
    cursor.execute("SELECT * FROM badges")
    all_badges = cursor.fetchall()
    badges_list = []
    for b in all_badges:
        b_dict = dict(b)
        b_dict["earned"] = b_dict["id"] in earned_dict
        b_dict["earned_at"] = earned_dict[b_dict["id"]]["earned_at"] if b_dict["earned"] else None
        badges_list.append(b_dict)

    profile["badges"] = badges_list
    conn.close()
    return profile

def record_activity_and_reward(user_id: str, action: str) -> Dict[str, Any]:
    """
    Rewards points and advances streak for verified eligible actions.
    Actions:
      - 'found_report': +10 points
      - 'verified_report': +20 points
      - 'successful_return': +50 points
    """
    points_map = {
        "found_report": 10,
        "verified_report": 20,
        "successful_return": 50
    }
    pts_to_add = points_map.get(action, 10)
    today_str = date.today().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gamification WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO gamification (user_id) VALUES (?)", (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM gamification WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

    prof = dict(row)
    current_streak = prof["current_streak"] or 0
    longest_streak = prof["longest_streak"] or 0
    last_act = prof["last_activity"]
    verified_reports = prof["verified_reports"] or 0
    successful_returns = prof["successful_returns"] or 0

    if action == "found_report" or action == "verified_report":
        verified_reports += 1
    elif action == "successful_return":
        successful_returns += 1

    # Streak logic: consecutive calendar days
    if last_act:
        last_date = datetime.strptime(last_act, "%Y-%m-%d").date()
        today_date = date.today()
        day_diff = (today_date - last_date).days

        if day_diff == 1:
            current_streak += 1
        elif day_diff > 1:
            current_streak = 1
        # if day_diff == 0, keep current streak
    else:
        current_streak = 1

    if current_streak > longest_streak:
        longest_streak = current_streak

    new_points = (prof["points"] or 0) + pts_to_add

    cursor.execute("""
    UPDATE gamification
    SET points = ?, current_streak = ?, longest_streak = ?,
        verified_reports = ?, successful_returns = ?, last_activity = ?
    WHERE user_id = ?
    """, (new_points, current_streak, longest_streak, verified_reports, successful_returns, today_str, user_id))

    # Badge awarding conditions:
    now_str = datetime.now().isoformat()
    # 1. First Finder: >= 1 verified found report
    if verified_reports >= 1:
        cursor.execute("INSERT OR IGNORE INTO user_badges (user_id, badge_id, earned_at) VALUES (?, 'first_finder', ?)", (user_id, now_str))
    # 2. Community Helper: >= 1 successful return
    if successful_returns >= 1:
        cursor.execute("INSERT OR IGNORE INTO user_badges (user_id, badge_id, earned_at) VALUES (?, 'community_helper', ?)", (user_id, now_str))
    # 3. 7-Day Helper: streak >= 7
    if current_streak >= 7:
        cursor.execute("INSERT OR IGNORE INTO user_badges (user_id, badge_id, earned_at) VALUES (?, 'streak_7', ?)", (user_id, now_str))
    # 4. 30-Day Helper: streak >= 30
    if current_streak >= 30:
        cursor.execute("INSERT OR IGNORE INTO user_badges (user_id, badge_id, earned_at) VALUES (?, 'streak_30', ?)", (user_id, now_str))
    # 5. Recovery Hero: successful_returns >= 3
    if successful_returns >= 3:
        cursor.execute("INSERT OR IGNORE INTO user_badges (user_id, badge_id, earned_at) VALUES (?, 'recovery_hero', ?)", (user_id, now_str))

    conn.commit()
    conn.close()
    return get_gamification_profile(user_id)

def get_leaderboard(limit: int = 15) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT g.*, u.name,
           (SELECT COUNT(*) FROM user_badges ub WHERE ub.user_id = g.user_id) as badges_count
    FROM gamification g
    JOIN users u ON g.user_id = u.id
    ORDER BY g.points DESC, g.successful_returns DESC
    LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    leaderboard = []
    for idx, r in enumerate(rows, start=1):
        d = dict(r)
        d["rank"] = idx
        leaderboard.append(d)
    return leaderboard

# Notifications Operations
def create_notification(user_id: str, title: str, message: str, notif_type: str = "info") -> str:
    notif_id = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO notifications (id, user_id, title, message, type, is_read, created_at)
    VALUES (?, ?, ?, ?, ?, 0, ?)
    """, (notif_id, user_id, title, message, notif_type, now_str))
    conn.commit()
    conn.close()
    return notif_id

def get_user_notifications(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM notifications
    WHERE user_id = ?
    ORDER BY created_at DESC
    LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_notification_read(notif_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()
    return True

# Admin Statistics
def get_admin_statistics() -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM items")
    total_reports = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM items WHERE type = 'lost'")
    lost_items = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM items WHERE type = 'found'")
    found_items = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM matches WHERE final_confidence >= 0.50")
    potential_matches = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM claims WHERE status = 'VERIFIED'")
    verified_claims = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM items WHERE status = 'RETURNED'")
    returned_items = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users")
    active_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM claims WHERE status = 'RETURNED'")
    successful_recoveries = cursor.fetchone()[0]
    
    cursor.execute("SELECT COALESCE(SUM(points), 0) FROM gamification")
    total_community_points = cursor.fetchone()[0]
    
    conn.close()

    rate = (successful_recoveries / total_reports * 100.0) if total_reports > 0 else 0.0

    return {
        "total_reports": total_reports,
        "lost_items": lost_items,
        "found_items": found_items,
        "potential_matches": potential_matches,
        "verified_claims": verified_claims,
        "returned_items": returned_items,
        "active_users": active_users,
        "successful_recoveries": successful_recoveries,
        "successful_recovery_rate": round(rate, 1),
        "total_community_points": total_community_points
    }

def list_all_matches(user_id: Optional[str] = None, limit: int = 20, min_confidence: float = 0.0) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT m.*, 
           l.title as lost_title, l.category as lost_category, l.location as lost_location, l.image_url as lost_image, l.user_id as lost_user_id,
           f.title as found_title, f.category as found_category, f.location as found_location, f.image_url as found_image, f.user_id as found_user_id,
           f.brand as found_brand, f.color as found_color, f.event_date as found_date, f.event_time as found_time,
           f.description as found_description, f.status as found_status
    FROM matches m
    JOIN items l ON m.lost_item_id = l.id
    JOIN items f ON m.found_item_id = f.id
    WHERE m.final_confidence >= ?
    """
    params = [min_confidence]
    if user_id:
        query += " AND (l.user_id = ? OR f.user_id = ?)"
        params.extend([user_id, user_id])
    query += " ORDER BY m.final_confidence DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["confidence_score"] = d.get("final_confidence", 0.0)
        d["image_score"] = d.get("image_similarity", 0.0)
        d["text_score"] = d.get("text_similarity", 0.0)
        d["location_score"] = d.get("location_similarity", 0.0)
        d["lost_item_title"] = d.get("lost_title")
        d["lost_item_category"] = d.get("lost_category")
        d["lost_item_location"] = d.get("lost_location")
        d["lost_item_image"] = d.get("lost_image")
        d["found_item_title"] = d.get("found_title")
        d["found_item_category"] = d.get("found_category")
        d["found_item_location"] = d.get("found_location")
        d["found_item_image"] = d.get("found_image")
        results.append(d)
    return results

def update_user_profile(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    allowed = ["name", "avatar_url"]
    fields = []
    values = []
    for k in allowed:
        if k in updates and updates[k] is not None:
            fields.append(f"{k} = ?")
            values.append(updates[k])
    if fields:
        values.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", tuple(values))
        conn.commit()
    conn.close()
    return get_user_by_id(user_id)

def update_user_password(user_id: str, new_hashed: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET hashed_password = ? WHERE id = ?", (new_hashed, user_id))
    conn.commit()
    conn.close()
    return True

def mark_all_notifications_read(user_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

