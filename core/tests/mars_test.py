import asyncio
from tools.audit.mars_auditor import mars_auditor

async def test_mars_breach():
    print("🧪 Testing MARS Boundary Breach Detection...")
    
    # 1. A UI task doing legitimate UI work
    ui_diff = """
    + <div className="p-4 bg-blue-500 hover:bg-blue-600 transition-colors">
    +   <span className="text-white font-bold">Submit</span>
    + </div>
    """
    is_on_curve, msg = mars_auditor.evaluate_boundary("ui", ui_diff)
    print(f"UI Task (Clean): {'✅' if is_on_curve else '❌'} {msg}")

    # 2. A UI task doing forbidden DB/Security work (The Breach)
    breach_diff = """
    + const db = await supabase.from('users').delete().match({ id: userId });
    + const token = jwt.sign({ admin: true }, process.env.SECRET);
    + localStorage.setItem('auth_token', token);
    """
    is_on_curve, msg = mars_auditor.evaluate_boundary("ui", breach_diff)
    print(f"UI Task (Breach): {'✅' if is_on_curve else '❌'} {msg}")

    # 3. A Security task doing Security work
    sec_diff = """
    + if (!verifyToken(token)) throw new AuthError("Invalid Session");
    + const hash = await bcrypt.hash(password, salt);
    """
    is_on_curve, msg = mars_auditor.evaluate_boundary("security", sec_diff)
    print(f"Security Task (Clean): {'✅' if is_on_curve else '❌'} {msg}")

if __name__ == "__main__":
    asyncio.run(test_mars_breach())
