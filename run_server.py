import sys
import traceback

if __name__ == "__main__":
    try:
        import api
        import uvicorn
        print("Successfully imported api module. Starting uvicorn...")
        uvicorn.run(api.app, host="0.0.0.0", port=8000)
    except Exception as e:
        print("CRITICAL ERROR: Failed to import api module!", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
