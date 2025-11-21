import asyncio
import os
import sys
import logging
from sqlalchemy import text

# Set API Key for testing (BEFORE imports)
os.environ["PAPPERS_API_KEY"] = "592b23c8aef6a9a4be892ed05d9ae1c0ff0d0ea0350b18e1"

# Add project root to path
sys.path.append(os.getcwd())

from app.db import SessionLocal, engine
from app.config import DATABASE_URL

print(f"DEBUG: DATABASE_URL = {DATABASE_URL}")
from app.services.geocoding_service import geocode_batch
from app.routers.api_geo_stats import get_etablissements_geo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_schema():
    """
    Manually add columns if they don't exist (simple migration)
    """
    db = SessionLocal()
    try:
        # Debug: List tables
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        tables = [row[0] for row in result]
        logger.info(f"Existing tables: {tables}")

        # Check if columns exist in Tous_PV
        try:
            db.execute(text("SELECT latitude FROM Tous_PV LIMIT 1"))
        except Exception:
            logger.info("Adding latitude/longitude to Tous_PV...")
            db.execute(text("ALTER TABLE Tous_PV ADD COLUMN latitude FLOAT"))
            db.execute(text("ALTER TABLE Tous_PV ADD COLUMN longitude FLOAT"))
            db.commit()

        # Check if columns exist in invitations
        try:
            # Check if table exists first
            db.execute(text("SELECT 1 FROM invitations LIMIT 1"))
            try:
                db.execute(text("SELECT latitude FROM invitations LIMIT 1"))
            except Exception:
                logger.info("Adding latitude/longitude to invitations...")
                db.execute(text("ALTER TABLE invitations ADD COLUMN latitude FLOAT"))
                db.execute(text("ALTER TABLE invitations ADD COLUMN longitude FLOAT"))
                db.commit()
        except Exception as e:
            logger.warning(f"Table 'invitations' not found or error: {e}. Skipping.")
            
        logger.info("Schema check passed.")
    except Exception as e:
        logger.error(f"Schema update failed: {e}")
        # Don't rollback everything if one fails, just continue for testing
    finally:
        db.close()

async def verify():
    print("--- Verifying Map Integration ---")
    
    # 1. Update Schema
    print("\n1. Checking Schema...")
    update_schema()
    
    # 2. Run Geocoding (Limit to 5 to be fast)
    print("\n2. Running Geocoding (limit=5)...")
    db = SessionLocal()
    try:
        # Check row count
        row_count = db.execute(text("SELECT COUNT(*) FROM Tous_PV")).scalar()
        print(f"   Rows in Tous_PV: {row_count}")
        
        if row_count > 0:
            try:
                count = await geocode_batch(db, limit=5)
                print(f"   Geocoded {count} establishments.")
            except Exception as e:
                print(f"   [PARTIAL ERROR] Geocoding service error (likely missing invitations table): {e}")
        else:
            print("   [WARNING] Tous_PV is empty. Cannot verify geocoding.")
            
    except Exception as e:
        print(f"   [ERROR] Geocoding failed: {e}")
    finally:
        db.close()

    # 3. Verify Geocoding Results Directly
    print("\n3. Verifying Geocoding Results in DB...")
    db = SessionLocal()
    try:
        # Check if any PV has lat/lon
        geocoded_count = db.execute(text("SELECT COUNT(*) FROM Tous_PV WHERE latitude IS NOT NULL")).scalar()
        print(f"   PVs with coordinates: {geocoded_count}")
        
        # Since we just geocoded random top PVEvents, we might not have one.
        # But we can test the call itself.
        results = get_etablissements_geo(q="Caisse", limit=10, db=db)
        print(f"   Got {len(results)} results for query 'Caisse'.")
        for r in results:
             print(f"   - {r['nom']} ({r['lat']}, {r['lng']})")
             
    except Exception as e:
        print(f"   [ERROR] API search failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify())
