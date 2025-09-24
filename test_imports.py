try:
    from backend.app.core.models import Base, User, RefreshToken, Study

    print("✅ All models imported successfully")
    print("Tables in Base.metadata:", Base.metadata.tables.keys())

    # Проверим, что Study правильно определена
    print("Study table name:", Study.__tablename__)
    print("Study columns:", [col.name for col in Study.__table__.columns])

except ImportError as e:
    print("❌ Import error:", e)
except Exception as e:
    print("❌ Other error:", e)