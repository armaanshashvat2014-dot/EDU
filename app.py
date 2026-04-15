import streamlit as st, os, time, re, uuid, json, concurrent.futures, base64
from pathlib import Path
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types
from google.cloud import firestore
from google.oauth2 import service_account
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

# -----------------------------
# 1) GLOBAL CONSTANTS & STYLING
# -----------------------------
st.set_page_config(page_title="helix.ai - Cambridge (CIE) Tutor", page_icon="📚", layout="centered")

quiz_bg_state = st.session_state.get("quiz_bg", "default")
if quiz_bg_state == "correct": bg_style = "radial-gradient(circle at 50% 50%, rgba(46, 204, 113, 0.25) 0%, #0a0a1a 80%)"
elif quiz_bg_state == "wrong": bg_style = "radial-gradient(circle at 50% 50%, rgba(231, 76, 60, 0.25) 0%, #0a0a1a 80%)"
else: bg_style = "radial-gradient(800px circle at 50% 0%, rgba(0, 212, 255, 0.12), rgba(0, 212, 255, 0.00) 60%), #0a0a1a"

st.markdown(f"""<style>
.stApp {{ background: {bg_style} !important; transition: background 0.6s ease-in-out; color: #f5f5f7 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important; }}
[data-testid="stSidebar"] {{ background: rgba(25, 25, 35, 0.4) !important; backdrop-filter: blur(40px) !important; border-right: 1px solid rgba(255, 255, 255, 0.08) !important; }}
[data-testid="stForm"],[data-testid="stVerticalBlockBorderWrapper"] {{ background: rgba(255, 255, 255, 0.04) !important; backdrop-filter: blur(40px) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 28px !important; padding: 24px !important; box-shadow: 0 16px 40px 0 rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important; margin: 20px 0 !important; }}
[data-testid="stChatMessage"] {{ background: rgba(255, 255, 255, 0.05) !important; backdrop-filter: blur(24px) !important; border: 1px solid rgba(255, 255, 255, 0.12) !important; border-radius: 28px !important; padding: 20px !important; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2) !important; color: #fff !important; margin-bottom: 16px; }}
[data-testid="stChatMessage"] * {{ color: #f5f5f7 !important; }}
.stTextInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>textarea, .stNumberInput>div>div>input {{ background: rgba(255, 255, 255, 0.05) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; border-radius: 12px !important; color: #fff !important; }} .stChatInputContainer {{ background: transparent !important; }}
.stButton>button {{ background: linear-gradient(180deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.02) 100%) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; border-radius: 20px !important; backdrop-filter: blur(20px) !important; color: #fff !important; font-weight: 600 !important; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important; }}
@media (hover: hover) and (pointer: fine) {{ .stButton>button:hover {{ background: linear-gradient(180deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.05) 100%) !important; border-color: rgba(255,255,255,0.4) !important; transform: translateY(-2px) !important; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4) !important; }} }}
.stButton>button:active {{ transform: translateY(1px) !important; background: rgba(255,255,255,0.2) !important; }}
.thinking-container {{ display: flex; align-items: center; gap: 8px; padding: 12px 16px; background-color: rgba(255,255,255,0.05); border-radius: 16px; margin: 10px 0; border-left: 3px solid #fc8404; backdrop-filter: blur(10px); }} .thinking-text {{ color: #fc8404; font-size: 14px; font-weight: 600; }} .thinking-dots {{ display: flex; gap: 4px; }} .thinking-dot {{ width: 6px; height: 6px; border-radius: 50%; background-color: #fc8404; animation: thinking-pulse 1.4s infinite; }} .thinking-dot:nth-child(2){{animation-delay: 0.2s;}} .thinking-dot:nth-child(3){{animation-delay: 0.4s;}} @keyframes thinking-pulse {{ 0%, 60%, 100% {{ opacity: 0.3; transform: scale(0.8); }} 30% {{ opacity: 1; transform: scale(1.2); }} }}
.big-title {{ font-family: 'Inter', sans-serif; color: #00d4ff; text-align: center; font-size: 48px; font-weight: 1200; letter-spacing: -3px; margin-bottom: 0px; text-shadow: 0 0 12px rgba(0, 212, 255, 0.4); }} .quiz-title {{ font-size: 32px; font-weight: 800; text-align: center; margin-bottom: 20px; }} .quiz-question-text {{ font-size: 28px; font-weight: 700; text-align: center; margin-bottom: 30px; line-height: 1.4; color: #fff; }} .quiz-counter {{ color: #a0a0ab; font-size: 14px; font-weight: 600; margin-bottom: 15px; }}
.glass-container {{ background: rgba(35, 35, 45, 0.4); backdrop-filter: blur(40px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 28px; padding: 24px; margin-bottom: 20px; }} .account-detail {{ font-size: 1.1rem; margin-bottom: 0.5rem; }} .mastery-title {{ font-size: 14px; color: #a0a0ab; font-weight: 600; text-transform: uppercase; margin-bottom: 8px; }} .mastery-value {{ font-size: 48px; color: #00d4ff; font-weight: 800; line-height: 1; }} .weak-spot-item {{ background: rgba(231, 76, 60, 0.1); border: 1px solid rgba(231, 76, 60, 0.2); border-radius: 16px; padding: 12px 16px; color: #f5f5f7; font-weight: 500; margin-bottom: 8px; }} .success-item {{ background: rgba(46, 204, 113, 0.1); border: 1px solid rgba(46, 204, 113, 0.2); border-radius: 16px; padding: 12px 16px; color: #f5f5f7; font-weight: 500; }}
[data-testid="stFileUploaderDropzone"] {{ z-index: -1 !important; }}
</style>""", unsafe_allow_html=True)

if "SCHOOL_CODES" in st.secrets: SCHOOL_CODES = dict(st.secrets["SCHOOL_CODES"])
else: SCHOOL_CODES = {}

# -----------------------------
# AI PROMPTS
# -----------------------------
SYSTEM_INSTRUCTION = f"""
You are Helix, an elite Cambridge (CIE) Tutor and Examiner for Grade 6-8 students.
RULE 1: STRICT SCOPE: Restrict ALL answers/questions ONLY to requested chapters. NEVER introduce outside concepts. "Hard" means multi-step reasoning, not outside topics.
RULE 2: Force multi-step reasoning. NEVER reveal the topic in the heading. Tables MUST be Markdown.
RULE 3: ANTI-PLAGIARISM: STRICTLY FORBIDDEN to copy-paste or slightly rephrase textbook questions. Generate 100% NEW/UNIQUE questions.
RULE 4: Use IMAGE_GEN:[Desc] or PIE_CHART:[L:V]. 
RULE 5: TITLE: # Helix A.I.\n## Practice Paper\n###[SUBJECT] - [GRADE]
RULE 6: If asked to evaluate weak points, silently do so. If detected, output at VERY END: ===ANALYTICS_START===\n{{ "subject": "Math", "grade": "Grade 7", "weak_point": "Fractions" }}\n===ANALYTICS_END===
RULE 7: Grade flexibly. SILENTLY solve first. Focus on SEMANTIC CORRECTNESS.
"""

QUIZ_SYSTEM_INSTRUCTION = f"""
You are an AI Quiz Engine. Output a single, raw JSON array of objects. NEVER output conversational text or markdown.
ANTI-PLAGIARISM & STRICT SYLLABUS BOUNDARIES: STRICTLY FORBIDDEN to copy from textbooks. Generate 100% NEW questions. NEVER introduce outside concepts.
JSON ARRAY Structure:[{{ "question": "?", "type": "MCQ", "options":["A", "B", "C", "D"], "correct_answer": "Exact option text", "explanation": "Why" }}]
"""
PAPER_SYSTEM = SYSTEM_INSTRUCTION + "\nCRITICAL FOR PAPERS: DO NOT output the ===ANALYTICS_START=== block. Append[PDF_READY] at the end."

GRADE_TO_STAGE = {"Grade 6": "Stage 7", "Grade 7": "Stage 8", "Grade 8": "Stage 9"}
STAGE_TO_GRADE = {v: k for k, v in GRADE_TO_STAGE.items()}
NUM_WORDS = {"six":"6","seven":"7","eight":"8","nine":"9","vi":"6","vii":"7","viii":"8","ix":"9"}
def normalize_stage_text(s: str) -> str:
    s = (s or "").lower()
    for w, d in NUM_WORDS.items(): s = re.sub(rf"\b{w}\b", d, s)
    return s

# -----------------------------
# AUTH & FIRESTORE
# -----------------------------
if hasattr(st, "user"): auth_object = st.user
elif hasattr(st, "experimental_user"): auth_object = st.experimental_user
else: st.error("Streamlit version too old for Google Login."); st.stop()
is_authenticated = getattr(auth_object, "is_logged_in", False)

@st.cache_resource
def get_firestore_client():
    if "firebase" in st.secrets: return firestore.Client(credentials=service_account.Credentials.from_service_account_info(dict(st.secrets["firebase"])))
    return None
db = get_firestore_client()

def get_student_class_data(student_email):
    if not db: return None
    for c in db.collection("classes").where(filter=firestore.FieldFilter("students", "array_contains", student_email)).limit(1).stream(): return {"id": c.id, **c.to_dict()}
    return None

def get_user_profile(email):
    if not db: return {"role": "student"}
    doc = db.collection("users").document(email).get()
    if doc.exists:
        p = doc.to_dict(); u = False
        if not p.get("display_name") and is_authenticated: p["display_name"] = getattr(auth_object, "name", email.split("@")[0]); u = True
        if p.get("role") == "undefined": p["role"] = "student"; u = True
        if u: db.collection("users").document(email).update(p)
        return p
    else:
        dp = {"role": "student", "teacher_id": None, "display_name": getattr(auth_object, "name", email.split("@")[0]) if is_authenticated else "Guest", "grade": "Grade 6", "school": None}
        db.collection("users").document(email).set(dp); return dp

def create_global_class(class_id, teacher_email, grade, section, school_name):
    clean_id = class_id.strip().upper()
    if not clean_id or not db: return False, "Database error."
    ref = db.collection("classes").document(clean_id)
    @firestore.transactional
    def check_and_create(transaction, r):
        if r.get(transaction=transaction).exists: return False, f"Class '{clean_id}' already exists!"
        transaction.set(r, {"created_by": teacher_email, "created_at": time.time(), "grade": grade, "section": section, "school": school_name, "students":[], "subjects":[]})
        return True, f"Class '{clean_id}' created successfully!"
    return check_and_create(db.transaction(), ref)

user_role = "guest"; user_profile = {} 
if is_authenticated:
    user_email = auth_object.email
    user_profile = get_user_profile(user_email)
    user_role = user_profile.get("role", "student")

@st.cache_data(ttl=600) 
def evaluate_weak_spots(_email): 
    if not db: return [],[]
    t = time.time() - 604800
    ws_ref = db.collection("users").document(_email).collection("weak_spots")
    act, dis = [],[]
    for d in ws_ref.where(filter=firestore.FieldFilter("identified_at", ">", t)).stream():
        v = d.to_dict(); v['id'] = d.id; (dis if v.get("dismissed") else act).append(v)
    rem =[d.to_dict() for d in db.collection("users").document(_email).collection("analytics").where(filter=firestore.FieldFilter("timestamp", ">", t)).stream() if d.to_dict().get("weak_point") and d.to_dict().get("weak_point").lower() != "none"]
    if len(rem) >= 3:
        p = f"Group semantic remarks: {json.dumps(rem)}. Ignore if in {[s.get('topic') for s in act+dis]}. Return ONLY JSON array of NEW distinct objects:[{{\"subject\": \"Math\", \"topic\": \"Fractions\"}}]"
        try:
            r = client.models.generate_content(model="gemini-2.5-flash", contents=p, config=types.GenerateContentConfig(temperature=0.1))
            if m := re.search(r'\[.*\]', safe_response_text(r), re.DOTALL):
                for s in json.loads(m.group(0)):
                    if s.get("topic") and s.get("subject"):
                        nd = ws_ref.add({"topic": s["topic"], "subject": s["subject"], "identified_at": time.time(), "dismissed": False})
                        act.append({"id": nd[1].id, "topic": s["topic"], "subject": s["subject"], "identified_at": time.time(), "dismissed": False})
        except: pass
    return act, dis

def run_quiz_weakpoint_check(history, email, subject):
    if not db: return
    p = f"Review the last 5 {subject} quiz answers:\n{json.dumps(history, indent=2)}\nSpecific recurring weak spot? Return JSON: {{\"weak_point\": \"desc\"}} or {{\"weak_point\": \"None\"}}"
    try:
        r = client.models.generate_content(model="gemini-2.5-flash-lite", contents=p, config=types.GenerateContentConfig(temperature=0.1))
        if m := re.search(r'\{.*\}', safe_response_text(r), re.DOTALL):
            d = json.loads(m.group(0))
            if d.get("weak_point") and d.get("weak_point").lower() != "none":
                db.collection("users").document(email).collection("analytics").add({"timestamp": time.time(), "subject": subject, "weak_point": d["weak_point"], "source": "quiz"})
    except: pass

def get_threads_collection(): return db.collection("users").document(auth_object.email).collection("threads") if is_authenticated and db else None
def get_all_threads():
    try: return[{"id": d.id, **d.to_dict()} for d in get_threads_collection().order_by("updated_at", direction=firestore.Query.DESCENDING).limit(15).stream()] if get_threads_collection() else[]
    except: return[]
def get_default_greeting(): return[{"role": "assistant", "content": "👋 **Hey there! I'm Helix!**\n\nI'm your CIE tutor here to help you ace your CIE exams! 📖\n\nI can answer your doubts, draw diagrams, and create quizzes!\n**Attach photos, PDFs, or text files directly in the chat box below!** 📸📄\n\nWhat are we learning today?", "is_greeting": True}]
def load_chat_history(thread_id):
    c = get_threads_collection()
    if c and thread_id:
        try:
            msgs =[m.to_dict() for m in c.document(thread_id).collection("messages").order_by("idx").stream()]
            if msgs: return msgs
            doc = c.document(thread_id).get()
            if doc.exists and "messages" in doc.to_dict(): return doc.to_dict().get("messages",[])
        except: pass
    return get_default_greeting()
def compress_image_for_db(b: bytes) -> str:
    try:
        if not b: return None
        i = Image.open(BytesIO(b)).convert('RGB'); i.thumbnail((1024, 1024), Image.Resampling.LANCZOS); b_io = BytesIO(); i.save(b_io, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(b_io.getvalue()).decode('utf-8')
    except: return None

def save_chat_history():
    c = get_threads_collection()
    if not c: return
    sm, ds, dg =[], set(), set()
    for msg in st.session_state.get("messages",[]):
        cs, r = str(msg.get("content", "")), msg.get("role")
        if r == "user":
            q = cs.lower()
            if any(k in q for k in["math", "algebra", "geometry", "calculate", "equation", "number", "fraction"]): ds.add("Math")
            if any(k in q for k in["science", "cell", "biology", "physics", "chemistry", "experiment", "gravity"]): ds.add("Science")
            if any(k in q for k in["english", "poem", "story", "essay", "writing", "grammar", "noun", "verb"]): ds.add("English")
            qn = normalize_stage_text(cs)
            if re.search(r"\b(stage\W*7|grade\W*6|class\W*6|year\W*6)\b", qn): dg.add("Grade 6")
            if re.search(r"\b(stage\W*8|grade\W*7|class\W*7|year\W*7)\b", qn): dg.add("Grade 7")
            if re.search(r"\b(stage\W*9|grade\W*8|class\W*8|year\W*8)\b", qn): dg.add("Grade 8")
        dbi =[compress_image_for_db(img) for img in msg.get("images",[]) if img] if msg.get("images") else msg.get("db_images",[])
        ub, um, un = None, msg.get("user_attachment_mime"), msg.get("user_attachment_name")
        if msg.get("user_attachment_bytes"):
            if "image" in (um or ""): ub = compress_image_for_db(msg["user_attachment_bytes"])
        elif msg.get("user_attachment_b64"): ub = msg.get("user_attachment_b64")
        smg = {"role": str(r), "content": cs, "is_greeting": bool(msg.get("is_greeting")), "is_downloadable": bool(msg.get("is_downloadable")), "db_images":[i for i in dbi if i], "image_models": msg.get("image_models",[])}
        if ub: smg["user_attachment_b64"], smg["user_attachment_mime"], smg["user_attachment_name"] = ub, um, un
        elif un: smg["user_attachment_name"], smg["user_attachment_mime"] = un, um
        sm.append(smg)
    try: 
        tr = c.document(st.session_state.get("current_thread_id")); tr.set({"updated_at": time.time(), "metadata": {"subjects": list(ds), "grades": list(dg)}}, merge=True)
        b = db.batch()
        for idx, s_msg in enumerate(sm):
            s_msg["idx"] = idx; b.set(tr.collection("messages").document(str(idx).zfill(4)), s_msg)
        b.commit()
    except Exception as e: st.toast(f"⚠️ DB Error: {e}")

api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
if not api_key: st.error("🚨 GOOGLE_API_KEY not found."); st.stop()
try: client = genai.Client(api_key=api_key)
except Exception as e: st.error(f"🚨 GenAI Error: {e}"); st.stop()

def generate_with_retry(model_target, contents, config, retries=2):
    fm = ["gemini-2.5-flash", "gemini-3.1-flash-preview", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite-preview"]
    mtt = [model_target] + [m for m in fm if m != model_target]
    for cm in mtt:
        for a in range(retries):
            try: return client.models.generate_content(model=cm, contents=contents, config=config)
            except Exception as e:
                es = str(e).lower()
                if any(x in es for x in ["503", "unavailable", "overloaded", "429", "quota"]):
                    if a < retries - 1: time.sleep(1.5 ** a); continue
                break 
        if cm != mtt[-1]: st.toast(f"⚠️ {cm} overloaded. Switching models...", icon="⚡")
    st.toast("🚨 All Google AI servers are currently overloaded.", icon="🛑")
    return None

def safe_response_text(resp) -> str:
    try: return str(resp.text) if getattr(resp, "text", None) else "\n".join([p.text for c in (getattr(resp, "candidates", []) or[]) for p in (getattr(c.content, "parts",[]) or[]) if getattr(p, "text", None)])
    except: return ""

def process_visual_wrapper(vp):
    el =[]
    try:
        vt, vd = vp
        if vt == "IMAGE_GEN":
            for m in['gemini-3-pro-image-preview', 'gemini-3.1-flash-image-preview', 'imagen-4.0-fast-generate-001', 'gemini-2.5-flash-image']:
                try:
                    if "imagen" in m.lower():
                        r = client.models.generate_images(model=m, prompt=vd, config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="4:3"))
                        if r.generated_images: return (r.generated_images[0].image.image_bytes, m, el)
                    else:
                        r = client.models.generate_content(model=m, contents=[f"{vd}\n\n(Important: Generate a 1k res image with a 4:3 aspect ratio.)"], config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
                        if r.candidates and r.candidates[0].content.parts:
                            for p in r.candidates[0].content.parts:
                                if getattr(p, "inline_data", None) and p.inline_data.data: return (p.inline_data.data, m, el)
                except Exception as e: el.append(f"**{m} Error:** {str(e)}")
            return (None, "All Models Failed", el)
        elif vt == "PIE_CHART":
            try:
                l, s =[],[]
                for i in str(vd).split(","):
                    if ":" in i: k, v = i.split(":", 1); l.append(k.strip()); s.append(float(re.sub(r"[^\d\.]", "", v)))
                if not l or not s or len(l) != len(s): return (None, "matplotlib_failed", el)
                f = Figure(figsize=(5, 5), dpi=200); FigureCanvas(f); ax = f.add_subplot(111)
                ax.pie(s, labels=l, autopct="%1.1f%%", startangle=140, colors=["#00d4ff", "#fc8404", "#2ecc71", "#9b59b6", "#f1c40f", "#e74c3c"][:len(l)], textprops={"color": "black", "fontsize": 9}); ax.axis("equal")
                b = BytesIO(); f.savefig(b, format="png", bbox_inches="tight", transparent=True); return (b.getvalue(), "matplotlib", el)
            except: return (None, "matplotlib_failed", el)
    except Exception as e: return (None, "Crash",[str(e)])

def md_inline_to_rl(text: str) -> str:
    s = (text or "").replace(r'\(', '').replace(r'\)', '').replace(r'\[', '').replace(r'\]', '').replace(r'\times', ' x ').replace(r'\div', ' ÷ ').replace(r'\circ', '°').replace(r'\pm', '±').replace(r'\leq', '≤').replace(r'\geq', '≥').replace(r'\neq', '≠').replace(r'\approx', '≈').replace(r'\pi', 'π').replace(r'\sqrt', '√').replace('\\', '')
    s = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1/\2', s).replace('$', '') 
    return re.sub(r"(?<!\*)\*(\S.+?)\*(?!\*)", r"<i>\1</i>", re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")))

def create_pdf(content: str, images=None, filename="Question_Paper.pdf"):
    b = BytesIO(); d = SimpleDocTemplate(b, pagesize=A4, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    sty = getSampleStyleSheet()
    ts = ParagraphStyle("CustomTitle", parent=sty["Heading1"], fontSize=18, textColor=colors.HexColor("#00d4ff"), spaceAfter=12, alignment=TA_CENTER, fontName="Helvetica-Bold")
    bs = ParagraphStyle("CustomBody", parent=sty["BodyText"], fontSize=11, spaceAfter=8, alignment=TA_LEFT, fontName="Helvetica")
    story, img_idx, tr =[], 0,[]

    def rnd_tbl():
        nonlocal tr
        if not tr: return
        nc = max(len(r) for r in tr)
        nr = [[Paragraph(md_inline_to_rl(c), bs) for c in list(r) + [""] * (nc - len(r))] for r in tr]
        t = Table(nr, colWidths=[d.width / max(1, nc)] * nc)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00d4ff")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "LEFT"), ("BOTTOMPADDING", (0, 0), (-1, 0), 8), ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fa")), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
        story.extend([t, Spacer(1, 0.18*inch)]); tr.clear()

    ls =[re.sub(r"\s*\(Source:.*?\)", "", l).strip() for l in str(content or "").split("\n") if "[PDF_READY]" not in l.upper() and not l.strip().startswith(("Source(s):", "**Source(s):**"))]
    for s in ls:
        if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
            cl =[c.strip() for c in s.split("|")[1:-1]]
            if not all(re.fullmatch(r":?-+:?", c) for c in cl if c): tr.append(cl)
            continue
        rnd_tbl()
        if not s: story.append(Spacer(1, 0.14*inch)); continue
        if s.startswith(("IMAGE_GEN:", "PIE_CHART:")):
            if images and img_idx < len(images) and images[img_idx]:
                try:
                    i_s = BytesIO(images[img_idx]); r_r = ImageReader(i_s); iw, ih = r_r.getSize()
                    story.extend([Spacer(1, 0.12*inch), RLImage(i_s, width=4.6*inch, height=4.6*inch*(ih/float(iw))), Spacer(1, 0.12*inch)])
                except: pass
            img_idx += 1; continue
        if s.startswith("# "): story.append(Paragraph(md_inline_to_rl(s[2:].strip()), ts))
        elif s.startswith("## "): story.append(Paragraph(md_inline_to_rl(s[3:].strip()), ParagraphStyle("CustomHeading", parent=sty["Heading2"], fontSize=14, spaceAfter=10, spaceBefore=10, fontName="Helvetica-Bold")))
        elif s.startswith("### "): story.append(Paragraph(f"<b>{md_inline_to_rl(s[4:].strip())}</b>", bs))
        else: story.append(Paragraph(md_inline_to_rl(s), bs))
    rnd_tbl(); story.extend([Spacer(1, 0.28*inch), Paragraph("<i>Generated by helix.ai</i>", bs)])
    d.build(story); b.seek(0); return b

def generate_chat_title(client, messages):
    try:
        um =[m.get("content", "") for m in messages if m.get("role") == "user"]
        if not um: return "New Chat"
        r = generate_with_retry("gemini-2.5-flash", ["Summarize into a short title (max 4 words). Context: " + "\n".join(um[-3:])], types.GenerateContentConfig(temperature=0.3, max_output_tokens=50))
        return safe_response_text(r).strip().replace('"', '').replace("'", "") or "New Chat"
    except: return "New Chat"

def guess_mime(fn: str, fb: str = "application/octet-stream") -> str: return "image/jpeg" if (fn or "").lower().endswith((".jpg", ".jpeg")) else "image/png" if (fn or "").lower().endswith(".png") else "application/pdf" if (fn or "").lower().endswith(".pdf") else fb
def is_image_mime(m: str) -> bool: return (m or "").lower().startswith("image/")

def upload_textbooks():
    af = {"sci":[], "math": [], "eng":[]}
    pm = {p.name.lower(): p for p in Path.cwd().rglob("*.pdf") if "cie" in p.name.lower()}
    cf = "fast_sync_cache.json"
    if os.path.exists(cf):
        try:
            with open(cf, "r") as f: cd = json.load(f)
            if time.time() - cd.get("timestamp", 0) < 86400:
                class CF:
                    def __init__(self, d): self.uri = d["uri"]; self.display_name = d["display_name"]
                for subj, files in cd["files"].items():
                    for i in files: af[subj].append(CF(i))
                return af
        except: pass
    
    try: ex = {f.display_name.lower(): f for f in client.files.list() if f.display_name}
    except: ex = {}
    
    def process_single_book(t):
        if t in ex and ex[t].state.name == "ACTIVE": return t, ex[t]
        if t in pm:
            try:
                up = client.files.upload(file=str(pm[t]), config={"mime_type": "application/pdf", "display_name": pm[t].name})
                timeout = time.time() + 90
                while up.state.name == "PROCESSING" and time.time() < timeout: time.sleep(3); up = client.files.get(name=up.name)
                if up.state.name == "ACTIVE": return t, up
            except Exception as e: print(f"Upload Error {t}: {e}")
        return t, None
        
    with st.chat_message("assistant"): st.markdown(f"""<div class="thinking-container"><span class="thinking-text">📚 Syncing {len(pm)} Books...</span><div class="thinking-dots"><div class="thinking-dot"></div><div class="thinking-dot"></div><div class="thinking-dot"></div></div></div>""", unsafe_allow_html=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: results = list(executor.map(process_single_book, list(pm.keys())))
        
    cd = {"sci": [], "math": [], "eng":[]}
    for t, fo in results:
        if fo:
            sk = "sci" if "sci" in t else "math" if "math" in t else "eng" if "eng" in t else None
            if sk: af[sk].append(fo); cd[sk].append({"uri": fo.uri, "display_name": fo.display_name})
                
    try:
        with open(cf, "w") as f: json.dump({"timestamp": time.time(), "files": cd}, f)
    except: pass
    return af

def select_relevant_books(q, fd, ug="Grade 6"):
    qn = normalize_stage_text(q)
    s7, s8, s9 = any(k in qn for k in["stage 7", "grade 6", "year 7"]), any(k in qn for k in["stage 8", "grade 7", "year 8"]), any(k in qn for k in["stage 9", "grade 8", "year 9"])
    im, isc, ien = any(k in qn for k in["math", "algebra", "number", "fraction", "geometry", "calculate", "equation"]), any(k in qn for k in["sci", "biology", "physics", "chemistry", "experiment", "cell", "gravity"]), any(k in qn for k in["eng", "poem", "story", "essay", "writing", "grammar"])
    if not (s7 or s8 or s9): s7, s8, s9 = (ug=="Grade 6"), (ug=="Grade 7"), (ug=="Grade 8")
    if not (im or isc or ien): im = isc = ien = True
    sel =[]
    def add(k, act):
        if act: 
            for b in fd.get(k,[]):
                n = b.display_name.lower()
                if "answers" in n and user_role != "teacher": continue
                if (s7 and "cie_7" in n) or (s8 and "cie_8" in n) or (s9 and "cie_9" in n): sel.append(b); return 
    add("math", im); add("sci", isc); add("eng", ien)
    return sel

def generate_full_quiz_ai(p, u_grade):
    pt = f"Create EXACTLY {p['num']} unique questions for a {p['grade']} {p['subj']} student. Topic: {p['chap']}. Difficulty: {p['diff']}."
    bs = select_relevant_books(f"{p['subj']} {p['grade']}", st.session_state.get("textbook_handles", {}), u_grade)
    ps =[]
    for b in bs: ps.extend([types.Part.from_text(text=f"[Source: {b.display_name}]"), types.Part.from_uri(file_uri=b.uri, mime_type="application/pdf")])
    ps.append(pt)
    r = generate_with_retry("gemini-2.5-flash", ps, types.GenerateContentConfig(system_instruction=QUIZ_SYSTEM_INSTRUCTION, temperature=0.7))
    if r:
        m = re.search(r'\[.*\]', safe_response_text(r), re.DOTALL)
        if m:
            try: return json.loads(m.group(0))
            except: pass
    return None

def evaluate_short_answer(q, ua, ref):
    pt = f"Evaluate short answer.\nQ: {q}\nAns: {ua}\nRef: {ref}\nOutput JSON: {{\n\"is_correct\": true/false,\n\"explanation\": \"feedback\"\n}}"
    try:
        r = client.models.generate_content(model="gemini-2.5-flash-lite", contents=pt, config=types.GenerateContentConfig(temperature=0.1))
        m = re.search(r'\{.*\}', safe_response_text(r), re.DOTALL)
        if m: return json.loads(m.group(0))
    except: pass
    return {"is_correct": False, "explanation": "Failed to evaluate answer."}
