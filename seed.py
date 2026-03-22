from database import get_db

with get_db() as db:
    cur = db.cursor()

    # Sample donors
    cur.executemany(
        "INSERT INTO donors (name, email, phone) VALUES (?, ?, ?)",
        [
            ("John Doe", "john@example.com", "08012345678"),
            ("Jane Smith", "jane@example.com", "08087654321"),
            ("Alice Johnson", "alice@example.com", "08123456789")
        ]
    )

    # Sample accounts
    cur.executemany(
        "INSERT INTO accounts (account_name, balance) VALUES (?, ?)",
        [
            ("Main Account", 5000),
            ("Project Fund", 12000)
        ]
    )

    # Sample transactions
    cur.executemany(
        "INSERT INTO transactions (date, account_name, type, amount, description) VALUES (?, ?, ?, ?, ?)",
        [
            ("2026-03-10", "Main Account", "Credit", 2000, "Donation received"),
            ("2026-03-11", "Project Fund", "Debit", 500, "Purchase of materials")
        ]
    )

    # Sample projects
    cur.executemany(
        "INSERT INTO projects (name, sector, budget) VALUES (?, ?, ?)",
        [
            ("Clean Water Project", "wash", 15000),
            ("School Feeding", "nutrition", 12000),
            ("Health Awareness Campaign", "health", 8000),
            ("Protection for Children", "protection", 10000),
            ("Adult Literacy Program", "education", 5000)
        ]
    )

    db.commit()
    print("Sample data inserted successfully.")