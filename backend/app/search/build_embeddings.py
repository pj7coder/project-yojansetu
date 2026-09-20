import argparse
import logging
import sys
import time

from app.database.session import SessionLocal
from app.embeddings.local_provider import LocalFastEmbedProvider
from app.search.indexer import SchemeSearchIndexService

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("yojansetu.search.build_embeddings")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild scheme search metadata and semantic vector embeddings.")
    parser.add_argument("--batch-size", type=int, default=32, help="Embedding batch size")
    args = parser.parse_args()

    logger.info("Starting verified scheme search metadata and embedding index build...")
    db = SessionLocal()
    start_time = time.time()
    try:
        provider = LocalFastEmbedProvider()
        if not provider.is_available():
            logger.error("Local embedding provider could not be initialized. Exiting.")
            sys.exit(1)

        result = SchemeSearchIndexService.rebuild_index(db, provider)
        elapsed = time.time() - start_time
        logger.info(f"Index build completed in {round(elapsed, 2)}s. Indexed: {result['indexed_count']} schemes.")

        status = SchemeSearchIndexService.get_index_status(db)
        logger.info(f"Current Index Status: {status}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
