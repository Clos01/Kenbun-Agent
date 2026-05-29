from tools.infrastructure.config import settings
from pydantic import SecretStr

def test_sovereign_config():
    print("--- 🏛️ Kenbun Sovereign Config Test ---")
    
    # 1. Test Project Root Discovery
    print(f"Project Root: {settings.PROJECT_ROOT}")
    assert settings.PROJECT_ROOT.exists(), "❌ PROJECT_ROOT does not exist!"
    
    # 2. Test Nested Settings (SIP)
    sip = settings.sip
    print(f"SIP Server: {sip.server}")
    print(f"SIP Username: {sip.username}")
    
    # 3. Test Secret Masking
    if sip.password:
        print(f"SIP Password (Masked): {sip.password}")
        # Verify it can be retrieved
        raw_pass = sip.password.get_secret_value()
        print(f"SIP Password (Length): {len(raw_pass)} chars")
        assert isinstance(sip.password, SecretStr), "❌ Password is not a SecretStr!"
    
    # 4. Test Chroma Settings
    chroma = settings.chroma
    print(f"Chroma Host: {chroma.host}")
    print(f"Chroma Port: {chroma.port}")
    
    # 5. Test Backward Compatibility
    from tools.infrastructure.config import CHROMA_PORT
    print(f"Backward Compatible CHROMA_PORT: {CHROMA_PORT}")
    assert CHROMA_PORT == chroma.port, "❌ Backward compatibility shim failed!"

    print("\n✅ Sovereign Configuration Verified: ALL PULSES NOMINAL.")

if __name__ == "__main__":
    try:
        test_sovereign_config()
    except Exception as e:
        print(f"❌ Verification Failed: {e}")
