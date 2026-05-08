import os

# Must be set before any test module is imported so vector_store reads the
# test directory instead of the production one.
os.environ["CHROMADB_DIR"] = "/tmp/p7-test-chromadb"
