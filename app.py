import streamlit as st
import os
import time
import re
import uuid
import json
import concurrent.futures
import base64
from pathlib import Path
from io import BytesIO
from PIL import Image

from google import genai
from google.genai import types
from google.cloud import firestore
from google.oauth2 import service_account

# ReportLab PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Image as RLImage, Table, TableStyle
)
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors

# Matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

# -----------------------------
# 1) GLOBAL CONSTANTS & STYLING
# -----------------------------
st.set_page_config(page_title="helix.ai - Cambridge (CIE) Tutor", page_icon="📚", layout="centered")

quiz_bg_state = st.session_state.get("quiz_bg", "default")
if quiz_bg_state == "correct":
    bg_style = "radial-gradient(circle at 50% 50%, rgba(46, 204, 113, 0.25) 0%, #0a0a1a 80%)"
elif quiz_bg_state == "wrong":
    bg_style = "radial-gradient(circle at 50% 50%, rgba(231, 76, 60, 0.25) 0%, #0a0a1a 80%)"
else:
    bg_style = "radial-gradient(800px circle at 50% 0%, rgba(0, 212, 255, 0.12), rgba(0, 212, 255, 0.00) 60%), #0a0a1a"

st.markdown(f"""
<style>
/* Core App Background & Typography */
.stApp {{ background: {bg_style} !important; transition: background 0.6s ease-in-out; color: #f5f5f7 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important; }}
/* Sidebar Glassmorphism */[data-testid="stSidebar"] {{ background: rgba(25, 25, 35, 0.4) !important; backdrop-filter: blur(40px) !important; -webkit-backdrop-filter: blur(40px) !important; border-right: 1px solid rgba(255, 255, 255, 0.08) !important; }}
/* Native Streamlit Form & Container Glass UI */[data-testid="stForm"],[data-testid="stVerticalBlockBorderWrapper"] {{ background: rgba(255, 255, 255, 0.04) !important; backdrop-filter: blur(40px) !important; -webkit-backdrop-filter: blur(40px) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 28px !important; padding: 24px !important; box-shadow: 0 16px 40px 0 rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important; margin: 20px 0 !important; }}
/* Glass Chat Bubbles */[data-testid="stChatMessage"] {{ background: rgba(255, 255, 255, 0.05) !important; backdrop-filter: blur(24px) !important; -webkit-backdrop-filter: blur(24px) !important; border: 1px solid rgba(255, 255, 255, 0.12) !important; border-radius: 28px !important; padding: 20px !important; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1) !important; color: #fff !important; margin-bottom: 16px; }}[data-testid="stChatMessage"] * {{ color: #f5f5f7 !important; }}
/* Glass Inputs (Chat & Forms) */.stTextInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>textarea, .stNumberInput>div>div>input {{ background: rgba(255, 255, 255, 0.05) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; border-radius: 12px !important; color: #fff !important; }} .stChatInputContainer {{ background: transparent !important; }}
/* Glossy Buttons */.stButton>button {{ background: linear-gradient(180deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.02) 100%) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; border-radius: 20px !important; backdrop-filter: blur(20px) !important; color: #fff !important; font-weight: 600 !important; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important; }}
/* Prevent Samsung mobile sticky hover bug! */@media (hover: hover) and (pointer: fine) {{ .stButton>button:hover {{ background: linear-gradient(180deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.05) 100%) !important; border-color: rgba(255,255,255,0.4) !important; transform: translateY(-2px) !important; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4) !important; }} }} .stButton>button:active {{ transform: translateY(1px) !important; background: rgba(255,255,255,0.2) !important; }}
/* Thinking Animation */.thinking-container {{ display: flex; align-items: center; gap: 8px; padding: 12px 16px; background-color: rgba(255,255,255,0.05); border-radius: 16px; margin: 10px 0; border-left: 3px solid #fc8404; backdrop-filter: blur(10px); }} .thinking-text {{ color: #fc8404; font-size: 14px; font-weight: 600; }} .thinking-dots {{ display: flex; gap: 4px; }} .thinking-dot {{ width: 6px; height: 6px; border-radius: 50%; background-color: #fc8404; animation: thinking-pulse 1.4s infinite; }} .thinking-dot:nth-child(2){{ animation-delay: 0.2s; }} .thinking-dot:nth-child(3){{ animation-delay: 0.4s; }} @keyframes thinking-pulse {{ 0%, 60%, 100% {{ opacity: 0.3; transform: scale(0.8); }} 30% {{ opacity: 1; transform: scale(1.2); }} }}
/* Typography */.big-title {{ font-family: 'Inter', sans-serif; color: #00d4ff; text-align: center; font-size: 48px; font-weight: 1200; letter-spacing: -3px; margin-bottom: 0px; text-shadow: 0 0 12px rgba(0, 212, 255, 0.4); }} .quiz-title {{ font-size: 32px; font-weight: 800; text-align: center; margin-bottom: 20px; }} .quiz-question-text {{ font-size: 28px; font-weight: 700; text-align: center; margin-bottom: 30px; line-height: 1.4; color: #fff; }} .quiz-counter {{ color: #a0a0ab; font-size: 14px; font-weight: 600; margin-bottom: 15px; }}
/* Account Page Glass UI */.glass-container {{ background: rgba(35, 35, 45, 0.4); backdrop-filter: blur(40px); -webkit-backdrop-filter: blur(40px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 28px; padding: 24px; margin-bottom: 20px; }} .account-detail {{ font-size: 1.1rem; margin-bottom: 0.5rem; }} .mastery-title {{ font-size: 14px; color: #a0a0ab; font-weight: 600; text-transform: uppercase; margin-bottom: 8px; }} .mastery-value {{ font-size: 48px; color: #00d4ff; font-weight: 800; line-height: 1; }} .weak-spot-item {{ background: rgba(231, 76, 60, 0.1); border: 1px solid rgba(231, 76, 60, 0.2); border-radius: 16px; padding: 12px 16px; color: #f5f5f7; font-weight: 500; margin-bottom: 8px; }} .success-item {{ background: rgba(46, 204, 113, 0.1); border: 1px solid rgba(46, 204, 113, 0.2); border-radius: 16px; padding: 12px 16px; color: #f5f5f7; font-weight: 500; }}[data-testid="stFileUploaderDropzone"] {{ z-index: -1 !important; }}
</style>
""", unsafe_allow_html=True)

if "SCHOOL_CODES" in st.secrets: SCHOOL_CODES = dict(st.secrets["SCHOOL_CODES"])
else: SCHOOL_CODES = {}

# -----------------------------
# AI PROMPTS
# -----------------------------
SYSTEM_INSTRUCTION = f"""
You are Helix, an elite Cambridge (CIE) Tutor and Examiner for Grade 6-8 students.

### RULE 1: RAG SEARCH & SCOPE (CRITICAL)
- Search the attached PDF textbooks using OCR FIRST.
- STRICT SCOPE: If the user requests specific chapters, you MUST STRICTLY RESTRICT all questions to ONLY those requested chapters.

### RULE 2: STRICT CAMBRIDGE QUESTION DEPTH
You MUST design questions that force multi-step reasoning. Do NOT explicitly use the word "HOTS".
- INDIRECT QUESTIONS: NEVER reveal the topic in the heading. The student MUST deduce the concept.
- TABLE FORMATTING: MUST use strict Markdown tables.

### RULE 3: ANTI-PLAGIARISM PROTOCOL (CRITICAL)
You are STRICTLY FORBIDDEN from copy-pasting or slightly rephrasing questions directly from the attached textbooks. The textbooks are for INSPIRATION ONLY. You must understand the concepts, style, and difficulty, then generate 100% NEW and UNIQUE questions that test the same skills.

### RULE 4: VISUAL SYNTAX (STRICT)
- YOU ARE CAPABLE OF GENERATING IMAGES. Use IMAGE_GEN:[Detailed description] or PIE_CHART:[Label1:Value1, Label2:Value2]. 

### RULE 5: MARK SCHEME & TITLE
- TITLE FORMAT: MUST be formatted EXACTLY like this:
# Helix A.I.
## Practice Paper
###[SUBJECT] - [GRADE]

### RULE 6: Analytics for students (HIDDEN):
If the user prompt explicitly asks you to evaluate for a weak point (e.g., every 6th message), silently do so.
If you detect a clear academic weak point, output a hidden analytics block at the VERY END wrapped exactly like this:
===ANALYTICS_START===
{{ "subject": "Math", "grade": "Grade 7", "weak_point": "Struggles with cross-multiplication in fractions" }}
===ANALYTICS_END===
If there is no clear weak point, DO NOT output this block.

### RULE 7: FLEXIBLE GRADING & CHAIN OF THOUGHT
When evaluating a student's typed chat answer, you MUST act as a supportive human tutor:
1. SILENTLY solve the problem yourself to determine the undeniable correct answer.
2. Focus ENTIRELY on SEMANTIC CORRECTNESS. 
3. NEVER penalize a student if their answer is longer or phrased differently.
"""

QUIZ_SYSTEM_INSTRUCTION = f"""
You are an AI Quiz Engine. Your ONLY job is to output a single, raw JSON array of objects based on the user's request. NEVER output conversational text or markdown formatting. 

### ANTI-PLAGIARISM & RANDOMIZATION (CRITICAL)
- STRICTLY FORBIDDEN to copy-paste or rephrase questions directly from the provided textbooks. Textbooks are for INSPIRATION ONLY.
- Generate 100% NEW, UNIQUE, and highly randomized questions. 

The JSON MUST be a valid ARRAY of objects. Each object MUST have this exact structure:
{{
    "question": "The text of the question?",
    "type": "MCQ", 
    "options":["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": "The exact text of the correct option",
    "explanation": "Brief explanation of why it is correct"
}}
"""
PAPER_SYSTEM = SYSTEM_INSTRUCTION + "\n\nCRITICAL FOR PAPERS: DO NOT output the ===ANALYTICS_START=== block. Append[PDF_READY] at the end."

GRADE_TO_STAGE = {"Grade 6": "Stage 7", "Grade 7": "Stage 8", "Grade 8": "Stage 9"}
STAGE_TO_GRADE = {v: k for k, v in GRADE_TO_STAGE.items()}
NUM_WORDS = {"six": "6", "seven": "7", "eight": "8", "nine": "9", "vi": "6", "vii": "7", "viii": "8", "ix": "9"}

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
    if "firebase" in st.secrets:
        creds = service_account.Credentials.from_service_account_info(dict(st.secrets["firebase"]))
        return firestore.Client(credentials=creds)
    return None

db = get_firestore_client()

def get_student_class_data(student_email):
    if not db: return None
    for c in db.collection("classes").where(filter=firestore.FieldFilter("students", "array_contains", student_email)).limit(1).stream(): return {"id": c.id, **c.to_dict()}
    return None

def get_user_profile(email):
    if not db: return {"role": "student"}
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()
    if doc.exists:
        profile = doc.to_dict()
        needs_update = False
        if not profile.get("display_name") and is_authenticated:
            profile["display_name"] = getattr(auth_object, "name", None) or email.split("@")[0]
            needs_update = True
        if profile.get("role") == "undefined":
            profile["role"] = "student"
            needs_update = True
        if needs_update: doc_ref.update(profile)
        return profile
    else:
        default_profile = {"role": "student", "teacher_id": None, "display_name": getattr(auth_object, "name", None) or email.split("@")[0] if is_authenticated else "Guest", "grade": "Grade 6", "school": None}
        doc_ref.set(default_profile)
        return default_profile

def create_global_class(class_id, teacher_email, grade, section, school_name):
    clean_id = class_id.strip().upper()
    if not clean_id or not db: return False, "Database error."
    class_ref = db.collection("classes").document(clean_id)
    @firestore.transactional
    def check_and_create(transaction, ref):
        snap = ref.get(transaction=transaction)
        if snap.exists: return False, f"Class '{clean_id}' already exists globally!"
        transaction.set(ref, {"created_by": teacher_email, "created_at": time.time(), "grade": grade, "section": section, "school": school_name, "students":[], "subjects":[]})
        return True, f"Class '{clean_id}' created successfully!"
    return check_and_create(db.transaction(), class_ref)

user_role = "guest"
user_profile = {} 
if is_authenticated:
    user_email = auth_object.email
    user_profile = get_user_profile(user_email)
    user_role = user_profile.get("role", "student")

# -----------------------------
# WEAK POINT AGGREGATION ENGINE
# -----------------------------
@st.cache_data(ttl=600) 
def evaluate_weak_spots(_email): 
    if not db: return [],[]
    now = time.time()
    seven_days_ago = now - (7 * 24 * 3600)
    
    ws_ref = db.collection("users").document(_email).collection("weak_spots")
    ws_docs = ws_ref.where(filter=firestore.FieldFilter("identified_at", ">", seven_days_ago)).stream()
    active_spots, dismissed_spots = [],[]
    for d in ws_docs:
        val = d.to_dict(); val['id'] = d.id
        if val.get("dismissed"): dismissed_spots.append(val)
        else: active_spots.append(val)
    
    an_ref = db.collection("users").document(_email).collection("analytics")
    an_docs = an_ref.where(filter=firestore.FieldFilter("timestamp", ">", seven_days_ago)).stream()
    
    raw_remarks =[d.to_dict() for d in an_docs if d.to_dict().get("weak_point") and d.to_dict().get("weak_point").lower() != "none"]
    
    if len(raw_remarks) >= 3:
        prompt = f"""
        You are a diagnostic AI. 
        Raw remarks about the student: {json.dumps(raw_remarks)}
        Active weak spots: {[s.get('topic') for s in active_spots]}
        Dismissed weak spots: {[s.get('topic') for s in dismissed_spots]}
        
        Task:
        1. Group the raw remarks by semantic similarity.
        2. If ANY group has 3 or more remarks, it is a "Potential Weak Spot".
        3. Output ONLY a JSON array of NEW distinct weak spot objects. You MUST identify the subject based on the raw remarks.
        Format Example: [{{"subject": "Math", "topic": "Fractions"}}]
        """
        try:
            resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=types.GenerateContentConfig(temperature=0.1))
            if match := re.search(r'\[.*\]', safe_response_text(resp), re.DOTALL):
                new_spots = json.loads(match.group(0))
                for spot in new_spots:
                    if spot.get("topic") and spot.get("subject"):
                        new_doc = ws_ref.add({"topic": spot["topic"], "subject": spot["subject"], "identified_at": now, "dismissed": False})
                        active_spots.append({"id": new_doc[1].id, "topic": spot["topic"], "subject": spot["subject"], "identified_at": now, "dismissed": False})
        except Exception as e: print("Weak spot engine error:", e)
            
    return active_spots, dismissed_spots

def run_quiz_weakpoint_check(history, email, subject):
    if not db: return
    prompt = f"Review the student's last 5 {subject} quiz answers:\n{json.dumps(history, indent=2)}\nDid they show a specific recurring weak spot? If yes, return JSON: {{\"weak_point\": \"description of weak spot\"}}. If no, return {{\"weak_point\": \"None\"}}."
    try:
        resp = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt, config=types.GenerateContentConfig(temperature=0.1))
        if match := re.search(r'\{.*\}', safe_response_text(resp), re.DOTALL):
            data = json.loads(match.group(0))
            if data.get("weak_point") and data.get("weak_point").lower() != "none":
                db.collection("users").document(email).collection("analytics").add({"timestamp": time.time(), "subject": subject, "weak_point": data["weak_point"], "source": "quiz"})
    except Exception: pass

# -----------------------------
# THREAD HELPERS
# -----------------------------
def get_threads_collection(): return db.collection("users").document(auth_object.email).collection("threads") if is_authenticated and db else None
def get_all_threads():
    coll_ref = get_threads_collection()
    if coll_ref:
        try: return[{"id": doc.id, **doc.to_dict()} for doc in coll_ref.order_by("updated_at", direction=firestore.Query.DESCENDING).limit(15).stream()]
        except Exception: pass
    return[]
def get_default_greeting(): return[{"role": "assistant", "content": "👋 **Hey there! I'm Helix!**\n\nI'm your friendly CIE tutor here to help you ace your CIE exams! 📖\n\nI can answer your doubts, draw diagrams, and create quizzes!\nYou can also **attach photos, PDFs, or text files directly in the chat box below!** 📸📄\n\nWhat are we learning today?", "is_greeting": True}]
def load_chat_history(thread_id):
    coll_ref = get_threads_collection()
    if coll_ref and thread_id:
        try:
            msgs_query = coll_ref.document(thread_id).collection("messages").order_by("idx").stream()
            msgs =[m.to_dict() for m in msgs_query]
            if msgs: return msgs
            doc = coll_ref.document(thread_id).get()
            if doc.exists and "messages" in doc.to_dict(): return doc.to_dict().get("messages",[])
        except Exception: pass
    return get_default_greeting()
def compress_image_for_db(image_bytes: bytes) -> str:
    try:
        if not image_bytes: return None
        img = Image.open(BytesIO(image_bytes)).convert('RGB')
        img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception: return None
def save_chat_history():
    coll_ref = get_threads_collection()
    if not coll_ref: return
    safe_messages, detected_subjects, detected_grades =[], set(), set()
    for msg in st.session_state.get("messages",[]):
        content_str = str(msg.get("content", ""))
        role = msg.get("role")
        if role == "user":
            q = content_str.lower()
            if any(k in q for k in["math", "algebra", "geometry", "calculate", "equation", "number", "fraction"]): detected_subjects.add("Math")
            if any(k in q for k in["science", "cell", "biology", "physics", "chemistry", "experiment", "gravity"]): detected_subjects.add("Science")
            if any(k in q for k in["english", "poem", "story", "essay", "writing", "grammar", "noun", "verb"]): detected_subjects.add("English")
            qn = normalize_stage_text(content_str)
            if re.search(r"\b(stage\W*7|grade\W*6|class\W*6|year\W*6)\b", qn): detected_grades.add("Grade 6")
            if re.search(r"\b(stage\W*8|grade\W*7|class\W*7|year\W*7)\b", qn): detected_grades.add("Grade 7")
            if re.search(r"\b(stage\W*9|grade\W*8|class\W*8|year\W*8)\b", qn): detected_grades.add("Grade 8")

        db_images =[]
        if msg.get("images"): db_images =[compress_image_for_db(img) for img in msg["images"] if img]
        elif msg.get("db_images"): db_images = msg["db_images"]

        user_attach_b64, user_attach_mime, user_attach_name = None, msg.get("user_attachment_mime"), msg.get("user_attachment_name")
        if msg.get("user_attachment_bytes"):
            if "image" in (user_attach_mime or ""): user_attach_b64 = compress_image_for_db(msg["user_attachment_bytes"])
        elif msg.get("user_attachment_b64"): user_attach_b64 = msg["user_attachment_b64"]

        safe_msg = {"role": str(role), "content": content_str, "is_greeting": bool(msg.get("is_greeting", False)), "is_downloadable": bool(msg.get("is_downloadable", False)), "db_images":[i for i in db_images if i], "image_models": msg.get("image_models",[])}
        if user_attach_b64: safe_msg["user_attachment_b64"], safe_msg["user_attachment_mime"], safe_msg["user_attachment_name"] = user_attach_b64, user_attach_mime, user_attach_name
        elif user_attach_name: safe_msg["user_attachment_name"], safe_msg["user_attachment_mime"] = user_attach_name, user_attach_mime
        safe_messages.append(safe_msg)

    try: 
        thread_ref = coll_ref.document(st.session_state.get("current_thread_id"))
        thread_ref.set({"updated_at": time.time(), "metadata": {"subjects": list(detected_subjects), "grades": list(detected_grades)}}, merge=True)
        batch = db.batch()
        for idx, s_msg in enumerate(safe_messages):
            s_msg["idx"] = idx 
            msg_ref = thread_ref.collection("messages").document(str(idx).zfill(4))
            batch.set(msg_ref, s_msg)
        batch.commit()
    except Exception as e: st.toast(f"⚠️ DB Error: {e}")

# -----------------------------
# GEMINI INIT
# -----------------------------
api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
if not api_key: st.error("🚨 GOOGLE_API_KEY not found."); st.stop()
try: client = genai.Client(api_key=api_key)
except Exception as e: st.error(f"🚨 GenAI Error: {e}"); st.stop()

def generate_with_retry(model_target, contents, config, retries=3):
    for attempt in range(retries):
        try: return client.models.generate_content(model=model_target, contents=contents, config=config)
        except Exception as e:
            err_str = str(e).lower()
            if "503" in err_str or "unavailable" in err_str or "overloaded" in err_str or "429" in err_str or "quota" in err_str:
                if attempt < retries - 1: time.sleep(1.5 ** attempt); continue
            try:
                st.toast(f"⚠️ {model_target} overloaded. Switching to high-speed fallback...", icon="⚡")
                fallback_model = "gemini-2.5-flash-lite" if "flash" in model_target else "gemini-2.5-flash"
                return client.models.generate_content(model=fallback_model, contents=contents, config=config)
            except Exception as fallback_e: raise fallback_e
    return None

def safe_response_text(resp) -> str:
    try: return str(resp.text) if getattr(resp, "text", None) else "\n".join([p.text for c in (getattr(resp, "candidates", []) or[]) for p in (getattr(c.content, "parts",[]) or[]) if getattr(p, "text", None)])
    except Exception: return ""

def process_visual_wrapper(vp):
    error_logs =[]
    try:
        v_type, v_data = vp
        if v_type == "IMAGE_GEN":
            for model_name in['gemini-3-pro-image-preview', 'gemini-3.1-flash-image-preview', 'imagen-4.0-fast-generate-001', 'gemini-2.5-flash-image']:
                try:
                    if "imagen" in model_name.lower():
                        result = client.models.generate_images(model=model_name, prompt=v_data, config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="4:3"))
                        if result.generated_images: return (result.generated_images[0].image.image_bytes, model_name, error_logs)
                    else:
                        result = client.models.generate_content(model=model_name, contents=[f"{v_data}\n\n(Important: Generate a 1k resolution image with a 4:3 aspect ratio.)"], config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
                        if result.candidates and result.candidates[0].content.parts:
                            for part in result.candidates[0].content.parts:
                                if getattr(part, "inline_data", None) and part.inline_data.data: return (part.inline_data.data, model_name, error_logs)
                except Exception as e: error_logs.append(f"**{model_name} Error:** {str(e)}")
            return (None, "All Models Failed", error_logs)
        elif v_type == "PIE_CHART":
            try:
                labels, sizes =[],[]
                for item in str(v_data).split(","):
                    if ":" in item:
                        k, v = item.split(":", 1)
                        labels.append(k.strip()); sizes.append(float(re.sub(r"[^\d\.]", "", v)))
                if not labels or not sizes or len(labels) != len(sizes): return (None, "matplotlib_failed", error_logs)
                fig = Figure(figsize=(5, 5), dpi=200); FigureCanvas(fig); ax = fig.add_subplot(111)
                ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140, colors=["#00d4ff", "#fc8404", "#2ecc71", "#9b59b6", "#f1c40f", "#e74c3c"][:len(labels)], textprops={"color": "black", "fontsize": 9}); ax.axis("equal")
                buf = BytesIO(); fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
                return (buf.getvalue(), "matplotlib", error_logs)
            except Exception as e: return (None, "matplotlib_failed", error_logs)
    except Exception as e: return (None, "Crash",[str(e)])

# -----------------------------
# PDF HELPER
# -----------------------------
def md_inline_to_rl(text: str) -> str:
    s = (text or "").replace(r'\(', '').replace(r'\)', '').replace(r'\[', '').replace(r'\]', '').replace(r'\times', ' x ').replace(r'\div', ' ÷ ').replace(r'\circ', '°').replace(r'\pm', '±').replace(r'\leq', '≤').replace(r'\geq', '≥').replace(r'\neq', '≠').replace(r'\approx', '≈').replace(r'\pi', 'π').replace(r'\sqrt', '√').replace('\\', '')
    s = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1/\2', s)
    s = s.replace('$', '') 
    return re.sub(r"(?<!\*)\*(\S.+?)\*(?!\*)", r"<i>\1</i>", re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")))

def create_pdf(content: str, images=None, filename="Question_Paper.pdf"):
    buffer = BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CustomTitle", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#00d4ff"), spaceAfter=12, alignment=TA_CENTER, fontName="Helvetica-Bold")
    body_style = ParagraphStyle("CustomBody", parent=styles["BodyText"], fontSize=11, spaceAfter=8, alignment=TA_LEFT, fontName="Helvetica")
    story, img_idx, table_rows =[], 0,[]

    def render_pending_table():
        nonlocal table_rows
        if not table_rows: return
        ncols = max(len(r) for r in table_rows)
        norm_rows = [[Paragraph(md_inline_to_rl(c), body_style) for c in list(r) + [""] * (ncols - len(r))] for r in table_rows]
        t = Table(norm_rows, colWidths=[doc.width / max(1, ncols)] * ncols)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00d4ff")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "LEFT"), ("BOTTOMPADDING", (0, 0), (-1, 0), 8), ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fa")), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
        story.extend([t, Spacer(1, 0.18*inch)]); table_rows =[]

    lines =[re.sub(r"\s*\(Source:.*?\)", "", l).strip() for l in str(content or "⚠️ No content").split("\n") if "[PDF_READY]" not in l.upper() and not l.strip().startswith(("Source(s):", "**Source(s):**"))]
    for s in lines:
        if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
            cells =[c.strip() for c in s.split("|")[1:-1]]
            if not all(re.fullmatch(r":?-+:?", c) for c in cells if c): table_rows.append(cells)
            continue
        render_pending_table()
        if not s: story.append(Spacer(1, 0.14*inch)); continue
        if s.startswith(("IMAGE_GEN:", "PIE_CHART:")):
            if images and img_idx < len(images) and images[img_idx]:
                try:
                    img_stream = BytesIO(images[img_idx]); rl_reader = ImageReader(img_stream)
                    iw, ih = rl_reader.getSize()
                    story.extend([Spacer(1, 0.12*inch), RLImage(img_stream, width=4.6*inch, height=4.6*inch*(ih/float(iw))), Spacer(1, 0.12*inch)])
                except Exception: pass
            img_idx += 1; continue
        if s.startswith("# "): story.append(Paragraph(md_inline_to_rl(s[2:].strip()), title_style))
        elif s.startswith("## "): story.append(Paragraph(md_inline_to_rl(s[3:].strip()), ParagraphStyle("CustomHeading", parent=styles["Heading2"], fontSize=14, spaceAfter=10, spaceBefore=10, fontName="Helvetica-Bold")))
        elif s.startswith("### "): story.append(Paragraph(f"<b>{md_inline_to_rl(s[4:].strip())}</b>", body_style))
        else: story.append(Paragraph(md_inline_to_rl(s), body_style))
    render_pending_table(); story.extend([Spacer(1, 0.28*inch), Paragraph("<i>Generated by helix.ai - Your CIE Tutor</i>", body_style)])
    doc.build(story); buffer.seek(0)
    return buffer

def generate_chat_title(client, messages):
    try:
        user_msgs =[m.get("content", "") for m in messages if m.get("role") == "user"]
        if not user_msgs: return "New Chat"
        response = generate_with_retry(model_target="gemini-2.5-flash", contents=["Summarize this into a short chat title (max 4 words). Context: " + "\n".join(user_msgs[-3:])], config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=50))
        return safe_response_text(response).strip().replace('"', '').replace("'", "") or "New Chat"
    except Exception as e: st.toast(f"Title Gen Failed: {e}"); return "New Chat"

# -----------------------------
# 3) DIALOGS & SESSION INIT
# -----------------------------
if "current_thread_id" not in st.session_state: st.session_state.current_thread_id = str(uuid.uuid4())
if "messages" not in st.session_state: st.session_state.messages = get_default_greeting()

@st.dialog("⚠️ Maximum Chats")
def confirm_new_chat_dialog(oldest_thread_id):
    st.write("Limit of 15 chats reached. Delete oldest to create new?")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True): st.rerun()
    if c2.button("Yes", type="primary", use_container_width=True):
        try: 
            thread_ref = get_threads_collection().document(oldest_thread_id)
            for m in thread_ref.collection("messages").stream(): m.reference.delete()
            thread_ref.delete()
        except Exception: pass
        st.session_state.current_thread_id = str(uuid.uuid4()); st.session_state.messages = get_default_greeting(); st.rerun()

@st.dialog("🗑️ Delete Chat")
def confirm_delete_chat_dialog(thread_id_to_delete):
    st.write("Permanently delete this chat?")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True): 
        st.session_state.delete_requested_for = None; st.rerun()
    if c2.button("Yes", type="primary", use_container_width=True):
        try:
            thread_ref = get_threads_collection().document(thread_id_to_delete)
            for m in thread_ref.collection("messages").stream(): m.reference.delete()
            thread_ref.delete()
        except Exception: pass
        if st.session_state.get("current_thread_id") == thread_id_to_delete: 
            st.session_state.current_thread_id = str(uuid.uuid4()); st.session_state.messages = get_default_greeting()
        st.session_state.delete_requested_for = None; st.rerun()

@st.dialog("Manage Class")
def manage_class_dialog_ui(class_id):
    new_id = st.text_input("Rename Class ID", value=class_id)
    if st.button("Save New ID", use_container_width=True):
        if db:
            old_ref = db.collection("classes").document(class_id)
            new_ref = db.collection("classes").document(new_id)
            new_ref.set(old_ref.get().to_dict())
            old_ref.delete()
            st.success("Renamed!"); time.sleep(1); st.rerun()
    st.error("Danger Zone")
    if st.button("Delete Class Permanently", type="primary", use_container_width=True):
        if db: db.collection("classes").document(class_id).delete()
        st.success("Deleted!"); time.sleep(1); st.rerun()

@st.dialog("Manage Student")
def manage_student_dialog_ui(student_email, class_id):
    prof = get_user_profile(student_email)
    new_name = st.text_input("Rename Student", value=prof.get("display_name", ""))
    if st.button("Save Name", use_container_width=True):
        if db: db.collection("users").document(student_email).update({"display_name": new_name})
        st.success("Renamed!"); time.sleep(1); st.rerun()
    st.error("Danger Zone")
    if st.button("Remove from Class", type="primary", use_container_width=True):
        if db:
            db.collection("classes").document(class_id).update({"students": firestore.ArrayRemove([student_email])})
            db.collection("users").document(student_email).update({"teacher_id": None})
        st.success("Removed!"); time.sleep(1); st.rerun()

@st.dialog("🔥 Delete Account Permanently")
def confirm_delete_account_dialog():
    st.warning("This action is irreversible. It will delete your account, all classes you created, and unlink you from all your students.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True): st.rerun()
    if c2.button("Yes, Delete My Account", type="primary", use_container_width=True):
        try:
            if db:
                for c in db.collection("classes").where(filter=firestore.FieldFilter("created_by", "==", user_email)).stream(): c.reference.delete()
                for s in db.collection("users").where(filter=firestore.FieldFilter("teacher_id", "==", user_email)).stream(): s.reference.update({"teacher_id": None})
                db.collection("users").document(user_email).delete()
            st.session_state.clear(); st.logout()
        except Exception as e: st.error(f"Error: {e}")

# -----------------------------
# 4) SIDEBAR
# -----------------------------
with st.sidebar:
    if not is_authenticated:
        st.markdown("Chatting as a Guest!\nLog in with Google to save history!")
        if st.button("Log in with Google", type="primary", use_container_width=True): st.login(provider="google")
    else:
        st.success(f"Welcome back, {user_profile.get('display_name', 'User')}!")
        
        if st.button("👤 My Account", use_container_width=True):
            st.session_state.view_mode = "account"
            st.rerun()
        if st.button("Log out", use_container_width=True):
            st.session_state.clear()
            st.logout()
            
        st.divider()
        
        if st.session_state.get("view_mode") == "account":
            if st.button("🔙 Back to App", use_container_width=True):
                st.session_state.view_mode = "main"
                st.rerun()
        
        if st.session_state.get("view_mode", "main") == "main":
            st.markdown("<b style='color:#00d4ff'>🎯 ACTIVE GRADE</b>", unsafe_allow_html=True)
            prof_grade = user_profile.get("grade", "Grade 6")
            active_grade = st.selectbox("Set your grade context",["Grade 6", "Grade 7", "Grade 8"], index=["Grade 6", "Grade 7", "Grade 8"].index(prof_grade), label_visibility="collapsed")
            if active_grade != prof_grade:
                if db: db.collection("users").document(user_email).update({"grade": active_grade})
                user_profile["grade"] = active_grade
                st.rerun()
            st.session_state.active_grade = active_grade
            st.divider()

            if user_role == "student":
                st.markdown("<b style='color:#00d4ff'>📱 APP MODE</b>", unsafe_allow_html=True)
                st.radio("Choose Mode",["💬 AI Tutor", "⚡ Interactive Quiz"], key="app_mode", label_visibility="collapsed")
                
                if st.session_state.get("app_mode") == "⚡ Interactive Quiz" and st.session_state.get("quiz_active"):
                    if st.button("End Quiz", use_container_width=True):
                        for key in list(st.session_state.keys()):
                            if key.startswith('quiz_'): del st.session_state[key]
                        st.session_state.app_mode = "💬 AI Tutor"
                        st.rerun()
                st.divider()

                if not user_profile.get("teacher_id"):
                    with st.expander("🎓 Are you a Teacher?"):
                        if st.button("Verify Code") and (code_input := st.text_input("Teacher Code", type="password")) in SCHOOL_CODES:
                            if db: db.collection("users").document(user_email).update({"role": "teacher", "school": SCHOOL_CODES[code_input]})
                            st.success("Verified!"); time.sleep(1); st.rerun()
                else:
                    c = get_student_class_data(user_email)
                    school_display = user_profile.get('school') or (c.get('school') if c else None) or "Not linked"
                    class_display = c.get('id', 'Unknown') if c else 'Unknown'
                    st.info(f"🏫 **School:** {school_display}\n\n**Class:** {class_display}")

    if st.session_state.get("view_mode", "main") == "main" and st.session_state.get("app_mode", "💬 AI Tutor") == "💬 AI Tutor" and user_role != "teacher":
        if st.button("➕ New Chat", use_container_width=True):
            st.session_state.current_thread_id = str(uuid.uuid4()); st.session_state.messages = get_default_greeting(); st.rerun()
        if is_authenticated:
            for t in get_all_threads():
                c1, c2 = st.columns([0.85, 0.15], vertical_alignment="center")
                if c1.button(f"{'🟢' if t['id'] == st.session_state.get('current_thread_id') else '💬'} {t.get('title', 'New Chat')}", key=f"btn_{t['id']}", use_container_width=True):
                    st.session_state.current_thread_id = t["id"]; st.session_state.messages = load_chat_history(t["id"]); st.rerun()
                if c2.button("⋮", key=f"set_{t['id']}", use_container_width=True): st.session_state.delete_requested_for = t['id']

if st.session_state.get("delete_requested_for"): confirm_delete_chat_dialog(st.session_state.get("delete_requested_for"))

def guess_mime(filename: str, fallback: str = "application/octet-stream") -> str:
    n = (filename or "").lower()
    return "image/jpeg" if n.endswith((".jpg", ".jpeg")) else "image/png" if n.endswith(".png") else "application/pdf" if n.endswith(".pdf") else fallback
def is_image_mime(m: str) -> bool: return (m or "").lower().startswith("image/")

@st.cache_resource(show_spinner=False)
def upload_textbooks():
    active_files = {"sci":[], "math": [], "eng":[]}
    pdf_map = {p.name.lower(): p for p in Path.cwd().rglob("*.pdf") if "cie" in p.name.lower()}
    target_files = list(pdf_map.keys())
    try: existing = {f.display_name.lower(): f for f in client.files.list() if f.display_name}
    except Exception: existing = {}
    with st.chat_message("assistant"): st.markdown(f"""<div class="thinking-container"><span class="thinking-text">📚 Synchronizing {len(target_files)} Textbooks...</span><div class="thinking-dots"><div class="thinking-dot"></div><div class="thinking-dot"></div><div class="thinking-dot"></div></div></div>""", unsafe_allow_html=True)
    def process_single_book(t):
        if t in existing and existing[t].state.name == "ACTIVE": return t, existing[t]
        if t in pdf_map:
            try:
                up = client.files.upload(file=str(pdf_map[t]), config={"mime_type": "application/pdf", "display_name": pdf_map[t].name})
                timeout = time.time() + 90
                while up.state.name == "PROCESSING" and time.time() < timeout: time.sleep(3); up = client.files.get(name=up.name)
                if up.state.name == "ACTIVE": return t, up
            except Exception as e: print(f"Upload Error {t}: {e}")
        return t, None
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_single_book, target_files))
    for t, file_obj in results:
        if file_obj:
            if "sci" in t: active_files["sci"].append(file_obj)
            elif "math" in t: active_files["math"].append(file_obj)
            elif "eng" in t: active_files["eng"].append(file_obj)
    return active_files

if is_authenticated and "textbook_handles" not in st.session_state:
    with st.spinner("Preparing curriculum..."): st.session_state.textbook_handles = upload_textbooks()

def select_relevant_books(query, file_dict, user_grade="Grade 6"):
    qn = normalize_stage_text(query)
    s7 = any(k in qn for k in["stage 7", "grade 6", "year 7"])
    s8 = any(k in qn for k in["stage 8", "grade 7", "year 8"])
    s9 = any(k in qn for k in["stage 9", "grade 8", "year 9"])
    im = any(k in qn for k in["math", "algebra", "number", "fraction", "geometry", "calculate", "equation"])
    isc = any(k in qn for k in["sci", "biology", "physics", "chemistry", "experiment", "cell", "gravity"])
    ien = any(k in qn for k in["eng", "poem", "story", "essay", "writing", "grammar"])
    if not (s7 or s8 or s9):
        if user_grade == "Grade 6": s7 = True
        elif user_grade == "Grade 7": s8 = True
        elif user_grade == "Grade 8": s9 = True
        else: s8 = True
    if not (im or isc or ien): im = isc = ien = True
    sel =[]
    def add(k, act):
        if act: 
            for b in file_dict.get(k,[]):
                n = b.display_name.lower()
                if "answers" in n and user_role != "teacher": continue
                if (s7 and "cie_7" in n) or (s8 and "cie_8" in n) or (s9 and "cie_9" in n): 
                    sel.append(b); return 
    add("math", im); add("sci", isc); add("eng", ien)
    return sel

def generate_full_quiz_ai(p, u_grade):
    prompt = f"Create EXACTLY {p['num']} unique questions for a {p['grade']} {p['subj']} student. Topic: {p['chap']}. Difficulty: {p['diff']}."
    books = select_relevant_books(f"{p['subj']} {p['grade']}", st.session_state.get("textbook_handles", {}), u_grade)
    parts =[]
    for b in books: parts.extend([types.Part.from_text(text=f"[Source: {b.display_name}]"), types.Part.from_uri(file_uri=b.uri, mime_type="application/pdf")])
    parts.append(prompt)
    resp = generate_with_retry("gemini-2.5-pro", parts, types.GenerateContentConfig(system_instruction=QUIZ_SYSTEM_INSTRUCTION, temperature=0.7))
    if resp:
        match = re.search(r'\[.*\]', safe_response_text(resp), re.DOTALL)
        if match:
            try: return json.loads(match.group(0))
            except Exception: pass
    return None

def evaluate_short_answer(question, user_ans, reference):
    prompt = f"Evaluate this short answer.\nQuestion: {question}\nStudent Answer: {user_ans}\nReference/Rubric: {reference}\nOutput ONLY valid JSON: {{\n\"is_correct\": true/false,\n\"explanation\": \"Short feedback\"\n}}"
    try:
        resp = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt, config=types.GenerateContentConfig(temperature=0.1))
        match = re.search(r'\{.*\}', safe_response_text(resp), re.DOTALL)
        if match: return json.loads(match.group(0))
    except Exception: pass
    return {"is_correct": False, "explanation": "Failed to evaluate answer."}

# ==========================================
# REUSABLE QUIZ UI (TEACHER & STUDENT)
# ==========================================
def render_quiz_engine():
    if not st.session_state.get("quiz_active", False):
        st.markdown("<div class='quiz-title'>⚙️ Quiz Engine</div>", unsafe_allow_html=True)
        tab_ai, tab_man, tab_join = st.tabs(["🤖 AI Generator", "✍️ Manual Builder", "🔑 Join Quiz"])
        
        with tab_ai:
            with st.form("create_quiz_form", border=False):
                with st.container(border=True):
                    st.markdown("<h3 style='text-align: center; margin-bottom:20px;'>Generate AI Quiz</h3>", unsafe_allow_html=True)
                    c1, c2, c3 = st.columns(3)
                    q_subj = c1.selectbox("Subject",["Math", "Science", "English", "Physics", "Chemistry", "Biology"])
                    current_active_grade = st.session_state.get("active_grade", user_profile.get("grade", "Grade 6"))
                    q_grade = c2.selectbox("Grade",["Grade 6", "Grade 7", "Grade 8"], index=["Grade 6", "Grade 7", "Grade 8"].index(current_active_grade))
                    q_diff = c3.selectbox("Difficulty",["Easy", "Medium", "Hard"])
                    
                    c4, c5 = st.columns([3, 1])
                    q_chap = c4.text_input("Chapter / Topic", placeholder="e.g., Chapter 4, Fractions, Forces...")
                    q_num = c5.selectbox("Questions",[5, 10, 15, 20])
                    
                col_btn1, col_btn2 = st.columns(2)
                start_quiz_btn = col_btn1.form_submit_button("🚀 Start Interactive Quiz", type="primary", use_container_width=True)
                gen_code_btn = col_btn2.form_submit_button("🔗 Generate ShareCode Only", use_container_width=True)
                
                if start_quiz_btn or gen_code_btn:
                    p = {"subj": q_subj, "grade": q_grade, "diff": q_diff, "chap": q_chap, "num": q_num}
                    with st.spinner("Generating your unique quiz... This may take up to 30 seconds."):
                        generated_q = generate_full_quiz_ai(p, current_active_grade)
                    
                    if generated_q:
                        share_code = str(uuid.uuid4())[:6].upper()
                        if db:
                            db.collection("quizzes").document(share_code).set({
                                "params": p, "questions": generated_q, "created_by": user_email, "created_at": time.time()
                            })
                        if start_quiz_btn:
                            st.session_state.quiz_params = p
                            st.session_state.quiz_questions = generated_q
                            st.session_state.quiz_score, st.session_state.quiz_current_q = 0, 1
                            st.session_state.quiz_active, st.session_state.quiz_saved = True, False
                            st.session_state.quiz_bg, st.session_state.quiz_history = "default",[]
                            st.session_state.quiz_share_code = share_code
                            st.rerun()
                        else:
                            st.success(f"Quiz generated! Share this code: **{share_code}**")
                    else: st.error("Failed to generate quiz. Please try again.")

        with tab_man:
            if "manual_questions" not in st.session_state: st.session_state.manual_questions =[]
            for i, mq in enumerate(st.session_state.get("manual_questions",[])):
                st.info(f"**Q{i+1}:** {mq['question']} *({mq['type']})*")
            
            with st.expander("➕ Add New Question", expanded=True):
                q_type = st.radio("Question Type", ["MCQ", "Short Answer"])
                q_text = st.text_area("Question Text")
                if q_type == "MCQ":
                    mc1, mc2 = st.columns(2)
                    opt_a = mc1.text_input("Option A")
                    opt_b = mc2.text_input("Option B")
                    opt_c = mc1.text_input("Option C")
                    opt_d = mc2.text_input("Option D")
                    correct_opt = st.selectbox("Correct Option",["Option A", "Option B", "Option C", "Option D"])
                    if st.button("Save MCQ"):
                        opts =[opt_a, opt_b, opt_c, opt_d]
                        c_text = opts[["Option A", "Option B", "Option C", "Option D"].index(correct_opt)]
                        st.session_state.manual_questions.append({
                            "question": q_text, "type": "MCQ", "options": opts, "correct_answer": c_text, "explanation": "Manual Quiz - Correct Answer."
                        })
                        st.rerun()
                else:
                    ref_ans = st.text_area("Reference Answer / Grading Rubric")
                    if st.button("Save Short Answer"):
                        st.session_state.manual_questions.append({
                            "question": q_text, "type": "Short Answer", "options":[], "correct_answer": ref_ans, "explanation": "Manual Quiz Evaluated."
                        })
                        st.rerun()

            if len(st.session_state.get("manual_questions",[])) > 0:
                if st.button("Publish Quiz & Get ShareCode", type="primary", use_container_width=True):
                    code = str(uuid.uuid4())[:6].upper()
                    if db:
                        db.collection("quizzes").document(code).set({
                            "questions": st.session_state.manual_questions,
                            "created_by": user_email,
                            "created_at": time.time(),
                            "params": {"subj": "Manual", "grade": "Mixed", "diff": "Mixed", "chap": "Mixed", "num": len(st.session_state.manual_questions)}
                        })
                    st.success(f"Quiz Published! ShareCode: **{code}**")
                    st.session_state.manual_questions =[]

        with tab_join:
            with st.form("join_quiz_form", border=False):
                with st.container(border=True):
                    st.markdown("<h3 style='text-align: center; margin-bottom:20px;'>Join a Shared Quiz</h3>", unsafe_allow_html=True)
                    share_code_input = st.text_input("Enter ShareCode", placeholder="e.g., A1B2C3").upper()
                    if st.form_submit_button("Join Quiz", use_container_width=True):
                        if db:
                            quiz_ref = db.collection("quizzes").document(share_code_input).get()
                            if quiz_ref.exists:
                                q_dict = quiz_ref.to_dict()
                                st.session_state.quiz_params = q_dict.get("params", {"subj": "General", "num": len(q_dict.get("questions",[]))})
                                st.session_state.quiz_questions = q_dict.get("questions",[])
                                st.session_state.quiz_share_code = share_code_input
                                st.session_state.quiz_score, st.session_state.quiz_current_q = 0, 1
                                st.session_state.quiz_active, st.session_state.quiz_saved = True, False
                                st.session_state.quiz_bg, st.session_state.quiz_history = "default",[]
                                st.rerun()
                            else:
                                st.error("Invalid ShareCode. Please check the code and try again.")
    else:
        # ACTIVE QUIZ
        q_list = st.session_state.get("quiz_questions",[])
        q_idx = st.session_state.get("quiz_current_q", 1) - 1
        if q_idx < len(q_list):
            q_data = q_list[q_idx]
            q_params = st.session_state.get("quiz_params", {})
            
            with st.container(border=True):
                st.markdown(f"<div class='quiz-counter'>Question {q_idx + 1} of {len(q_list)}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='quiz-question-text'>{q_data.get('question', 'Question text missing')}</div>", unsafe_allow_html=True)

                if st.session_state.get("quiz_user_answer") is None:
                    if q_data.get("type", "MCQ") == "MCQ":
                        for option in q_data.get('options',[]):
                            if st.button(option, use_container_width=True, key=f"q_opt_{option}"):
                                st.session_state.quiz_user_answer = option; st.rerun()
                    else:
                        user_sa = st.text_area("Your Answer:")
                        if st.button("Submit Answer", type="primary"):
                            with st.spinner("Evaluating..."):
                                eval_res = evaluate_short_answer(q_data.get("question"), user_sa, q_data.get("correct_answer"))
                                st.session_state.quiz_sa_eval = eval_res
                            st.session_state.quiz_user_answer = user_sa; st.rerun()
                else:
                    user_ans = st.session_state.get("quiz_user_answer")
                    
                    if q_data.get("type", "MCQ") == "MCQ":
                        is_correct = (user_ans == q_data.get('correct_answer'))
                        explanation = q_data.get('explanation', '')
                    else:
                        eval_res = st.session_state.get("quiz_sa_eval", {})
                        is_correct = eval_res.get("is_correct", False)
                        explanation = eval_res.get("explanation", "Evaluated by AI.")

                    if is_correct:
                        st.success(f"**Correct!** {explanation}")
                        if st.session_state.get("quiz_bg") != "correct":
                            st.session_state.quiz_score += 1
                            st.session_state.quiz_bg = "correct"; st.rerun()
                    else:
                        if q_data.get("type", "MCQ") == "MCQ": st.error(f"**Incorrect.** The correct answer was **{q_data.get('correct_answer')}**. \n\n*Explanation: {explanation}*")
                        else: st.error(f"**Incorrect.** \n\n*Feedback: {explanation}*")
                        if st.session_state.get("quiz_bg") != "wrong":
                            st.session_state.quiz_bg = "wrong"; st.rerun()
                            
                    if len(st.session_state.get("quiz_history",[])) < st.session_state.get("quiz_current_q"):
                        st.session_state.quiz_history.append({"q": q_data.get('question'), "user": user_ans, "correct": q_data.get('correct_answer'), "is_correct": is_correct})
                        if len(st.session_state.quiz_history) % 5 == 0: run_quiz_weakpoint_check(st.session_state.quiz_history[-5:], user_email, q_params.get('subj', 'General'))

                    is_last_q = (st.session_state.get("quiz_current_q") == len(q_list))
                    if st.button("Next Question" if not is_last_q else "Finish Quiz", type="primary", use_container_width=True):
                        if is_last_q: st.session_state.quiz_finished = True
                        else: st.session_state.quiz_current_q += 1
                        st.session_state.quiz_user_answer = None 
                        st.session_state.quiz_bg = "default"; st.rerun()

        if st.session_state.get("quiz_finished"):
            score, total = st.session_state.get("quiz_score"), len(st.session_state.get("quiz_questions",[]))
            if not st.session_state.get("quiz_saved") and is_authenticated and db:
                db.collection("users").document(user_email).collection("quiz_results").add({"timestamp": time.time(), "score": score, "total": total, "subject": st.session_state.get("quiz_params", {}).get('subj', 'Manual')})
                st.session_state.quiz_saved = True
                
            st.balloons()
            st.success(f"## 🎉 Quiz Complete! 🎉 \n\n### You scored: {score} / {total}")
            if st.session_state.get("quiz_share_code"):
                st.info(f"Challenge friends with ShareCode: **{st.session_state.get('quiz_share_code')}**")
                
            if st.button("Take Another Quiz", use_container_width=True):
                for key in list(st.session_state.keys()):
                    if key.startswith('quiz_'): del st.session_state[key]
                st.rerun()

# ==========================================
# APP ROUTER
# ==========================================
render_chat_interface = False 
view_mode = st.session_state.get("view_mode", "main")
app_mode = st.session_state.get("app_mode", "💬 AI Tutor")

# --- 1) ACCOUNT DASHBOARD (ALL ROLES) ---
if view_mode == "account":
    render_chat_interface = False
    st.markdown("<div class='big-title' style='display: flex; align-items: center; justify-content: center; gap: 15px;'><svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' class='feather feather-user'><path d='M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2'></path><circle cx='12' cy='7' r='4'></circle></svg> My Account</div><br>", unsafe_allow_html=True)
    
    student_class_data = get_student_class_data(user_email)
    class_name = student_class_data.get('id') if student_class_data else "Not in a Class"
    school_name = user_profile.get('school') or (student_class_data.get('school') if student_class_data else None) or "Not linked"

    with st.container():
        st.markdown(f"""<div class="glass-container">
            <div class="account-detail"><b>Name:</b> {user_profile.get('display_name', 'Guest')}</div>
            <div class="account-detail"><b>Email:</b> {user_email}</div>
            <div class="account-detail"><b>Grade:</b> {user_profile.get('grade', 'Grade 6')}</div>
            <div class="account-detail"><b>School:</b> {school_name}</div>
            {f'<div class="account-detail"><b>Class:</b> {class_name}</div>' if user_role == 'student' else ''}
        </div>""", unsafe_allow_html=True)

        with st.form("rename_form", border=False):
            st.markdown("<div class='glass-container'>", unsafe_allow_html=True)
            new_name = st.text_input("Change Display Name", value=user_profile.get('display_name', ''))
            if st.form_submit_button("Save Name", use_container_width=True):
                if db: db.collection("users").document(user_email).update({"display_name": new_name})
                st.success("Name updated!"); time.sleep(1); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        
        if user_role == "teacher":
            st.markdown("### Danger Zone")
            with st.container(border=True):
                if st.button("Request Account Deletion", type="primary", use_container_width=True):
                    confirm_delete_account_dialog()

    if user_role == "student":
        scores, totals = 0, 0
        if db:
            qr_docs = db.collection("users").document(user_email).collection("quiz_results").stream()
            for qd in qr_docs: d = qd.to_dict(); scores += d.get("score", 0); totals += d.get("total", 0)
        mastery = int((scores/totals)*100) if totals > 0 else 0
        
        st.markdown(f"""<div class="glass-container"><div class="mastery-title">Overall Mastery</div><div class="mastery-value">{mastery}%</div></div>""", unsafe_allow_html=True)
        st.markdown("### ⚠️ Potential Weak Spots (7 Days)")
        with st.spinner("Analyzing recent performance..."):
            active_spots, _ = evaluate_weak_spots(user_email)
        
        if not active_spots: st.markdown("<div class='success-item'>No active weak spots detected! Great job! 🎉</div>", unsafe_allow_html=True)
        else:
            for spot in active_spots:
                col1, col2 = st.columns([0.8, 0.2])
                with col1: st.markdown(f"<div class='weak-spot-item'>[{spot.get('subject', 'General')}] {spot['topic']}</div>", unsafe_allow_html=True)
                with col2:
                    if st.button("Dismiss", key=f"d_a_{spot['id']}", use_container_width=True):
                        if db: db.collection("users").document(user_email).collection("weak_spots").document(spot['id']).update({"dismissed": True})
                        st.rerun()

# --- 2) TEACHER DASHBOARD ---
elif user_role == "teacher":
    st.markdown("<div class='big-title' style='color:#fc8404;'>👨‍🏫 helix.ai / Teacher</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    roster =[]
    if db:
        if user_profile.get("school"): roster_stream = db.collection("users").where(filter=firestore.FieldFilter("school", "==", user_profile.get("school"))).stream()
        else: roster_stream = db.collection("users").where(filter=firestore.FieldFilter("teacher_id", "==", user_email)).stream()
        roster =[u for u in roster_stream if u.to_dict().get("role") == "student"]

    teacher_menu = st.radio("Menu",["Student Analytics", "Class Management", "Assign Papers", "⚡ Interactive Quiz", "💬 AI Chat"], horizontal=True, label_visibility="collapsed")
    st.divider()

    if teacher_menu == "Student Analytics":
        st.subheader("📊 Student Analytics")
        if not roster: st.info("No students enrolled yet.")
        else:
            selected_student_name = st.selectbox("Select Student",[r.to_dict().get('display_name', r.id) for r in roster])
            student_doc_list =[r for r in roster if r.to_dict().get('display_name', r.id) == selected_student_name]
            if student_doc_list:
                stu_email = student_doc_list[0].id
                stu_class_data = get_student_class_data(stu_email)
                class_subjects = stu_class_data.get("subjects",[]) if stu_class_data else[]
                
                st.markdown("#### Subject-Specific Mastery")
                if not class_subjects: st.info("No subjects assigned to this student's class.")
                else:
                    cols = st.columns(len(class_subjects))
                    for i, subject in enumerate(class_subjects):
                        scores, totals = 0, 0
                        if db:
                            qr_docs = db.collection("users").document(stu_email).collection("quiz_results").where(filter=firestore.FieldFilter("subject", "==", subject)).stream()
                            for qd in qr_docs: d = qd.to_dict(); scores += d.get("score", 0); totals += d.get("total", 0)
                        mastery = int((scores/totals)*100) if totals > 0 else 0
                        cols[i].metric(f"{subject}", f"{mastery}%")
                
                st.markdown("### ⚠️ Potential Weak Spots (7 Days)")
                with st.spinner("Analyzing recent performance..."):
                    active_spots, _ = evaluate_weak_spots(stu_email)
                
                relevant_spots =[s for s in active_spots if s.get('subject') in class_subjects] if class_subjects else active_spots
                
                if not relevant_spots: st.success("No active weak spots detected for your subjects!")
                else:
                    for spot in relevant_spots:
                        col1, col2 = st.columns([0.8, 0.2])
                        col1.warning(f"[{spot.get('subject', 'General')}] {spot['topic']}")
                        if col2.button("Dismiss", key=f"d_t_{spot['id']}"):
                            if db: db.collection("users").document(stu_email).collection("weak_spots").document(spot['id']).update({"dismissed": True})
                            st.rerun()

    elif teacher_menu == "Class Management":
        st.subheader("🏫 Class Management")
        with st.form("create_class_form", border=False):
            st.markdown("<div class='glass-container'>", unsafe_allow_html=True)
            st.markdown("<h5>Create New Class</h5>", unsafe_allow_html=True)
            cc1, cc2, cc3 = st.columns([0.4, 0.3, 0.3])
            grade_choice = cc1.selectbox("Grade",["Grade 6", "Grade 7", "Grade 8"])
            section_choice = cc2.selectbox("Section", ["A", "B", "C", "D"])
            if cc3.form_submit_button("Create", use_container_width=True):
                success, msg = create_global_class(f"{grade_choice.split()[-1]}{section_choice}".upper(), user_email, grade_choice, section_choice, user_profile.get("school"))
                if success: st.success(msg); time.sleep(1); st.rerun()
                else: st.error(msg)
            st.markdown("</div>", unsafe_allow_html=True)
            
        my_classes = list(db.collection("classes").where(filter=firestore.FieldFilter("created_by", "==", user_email)).stream()) if db else[]
        if my_classes:
            st.markdown("---")
            st.subheader("Edit Existing Class")
            for c_doc in my_classes:
                c_data = c_doc.to_dict()
                col1, col2 = st.columns([0.85, 0.15])
                if col1.button(f"🏫 {c_doc.id}", key=f"sel_cls_{c_doc.id}", use_container_width=True): st.session_state.managing_class = c_doc.id
                if col2.button("⋮", key=f"del_cls_{c_doc.id}"): manage_class_dialog_ui(c_doc.id)
                    
            if st.session_state.get("managing_class"):
                m_class_id = st.session_state.get("managing_class")
                if db:
                    m_class_doc = db.collection("classes").document(m_class_id).get()
                    if m_class_doc.exists:
                        c_data = m_class_doc.to_dict()
                        with st.form(f"edit_subjects_{m_class_id}", border=False):
                            st.markdown("<div class='glass-container'>", unsafe_allow_html=True)
                            subjects = st.multiselect(f"Subjects taught in {m_class_id}",["Math", "Science", "English", "Physics", "Chemistry", "Biology"], default=c_data.get("subjects",[]))
                            if st.form_submit_button("Update Subjects", use_container_width=True):
                                db.collection("classes").document(m_class_id).update({"subjects": subjects})
                                st.success("Subjects updated!"); time.sleep(1); st.rerun()
                            st.markdown("</div>", unsafe_allow_html=True)
                        
                        st.markdown("<h6>Student Roster</h6>", unsafe_allow_html=True)
                        for s_email in c_data.get("students",[]):
                            s_prof = get_user_profile(s_email)
                            c1, c2 = st.columns([0.85, 0.15], vertical_alignment="center")
                            c1.markdown(f"<div class='glass-container' style='padding:10px; margin-bottom:5px;'>{s_prof.get('display_name', 'Unknown')} ({s_email})</div>", unsafe_allow_html=True)
                            if c2.button("⋮", key=f"mng_stu_{s_email}"): manage_student_dialog_ui(s_email, m_class_id)
                        
                        with st.form(f"add_student_{m_class_id}", border=False):
                            st.markdown("<div class='glass-container'>", unsafe_allow_html=True)
                            em = st.text_input("Add Student Email")
                            if st.form_submit_button("Add Student", use_container_width=True) and em:
                                db.collection("users").document(em.strip().lower()).set({"role": "student", "teacher_id": user_email, "school": user_profile.get("school")}, merge=True)
                                db.collection("classes").document(m_class_id).update({"students": firestore.ArrayUnion([em.strip().lower()])})
                                st.success("Added!"); time.sleep(1); st.rerun()
                            st.markdown("</div>", unsafe_allow_html=True)

    elif teacher_menu == "Assign Papers":
        st.subheader("📝 Assignment Creator")
        with st.form("assign_paper_form", border=False):
            st.markdown("<div class='glass-container'>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            assign_title, assign_subject, assign_grade = c1.text_input("Title", "Chapter Quiz"), c1.selectbox("Subject",["Math", "Science", "Biology", "Chemistry", "Physics", "English"]), c1.selectbox("Grade",["Grade 6", "Grade 7", "Grade 8"])
            assign_difficulty, assign_marks, assign_extra = c2.selectbox("Difficulty",["Easy", "Medium", "Hard"]), c2.number_input("Marks", 10, 100, 30, 5), st.text_area("Extra Instructions")
            if st.form_submit_button("🤖 Generate with Helix AI", type="primary", use_container_width=True):
                with st.spinner("Writing paper..."):
                    books = select_relevant_books(f"{assign_subject} {assign_grade}", st.session_state.get("textbook_handles", {}), assign_grade)
                    parts =[]
                    for b in books: parts.extend([types.Part.from_text(text=f"[Source: {b.display_name}]"), types.Part.from_uri(file_uri=b.uri, mime_type="application/pdf")])
                    parts.append(types.Part.from_text(text=f"Task: Generate a CIE {assign_subject} paper for {assign_grade} students.\nDifficulty: {assign_difficulty}. Marks: {assign_marks}.\nExtra Instructions: {assign_extra}"))
                    try:
                        resp = generate_with_retry("gemini-2.5-pro", parts, types.GenerateContentConfig(system_instruction=PAPER_SYSTEM, temperature=0.1))
                        gen_paper = safe_response_text(resp)
                        draft_imgs, draft_mods = [],[]
                        if v_prompts := re.findall(r"(IMAGE_GEN|PIE_CHART):\s*\[(.*?)\]", gen_paper):
                            with concurrent.futures.ThreadPoolExecutor(5) as exe:
                                for r in exe.map(process_visual_wrapper, v_prompts):
                                    draft_imgs.append(r[0]); draft_mods.append(r[1])
                                    if not r[0] and len(r)>2: st.error(f"Image Error: {r[2]}")
                        st.session_state.update({"draft_paper": gen_paper, "draft_images": draft_imgs, "draft_models": draft_mods, "draft_title": assign_title}); st.rerun()
                    except Exception as e: st.error(e)
            st.markdown("</div>", unsafe_allow_html=True)
            
        if st.session_state.get("draft_paper"):
            with st.expander("Preview", expanded=True):
                st.markdown(st.session_state.get("draft_paper").replace("[PDF_READY]", ""))
                if st.session_state.get("draft_images"):
                    for i, m in zip(st.session_state.get("draft_images"), st.session_state.get("draft_models")):
                        if i: st.image(i, caption=m)
                try: st.download_button("Download PDF", data=create_pdf(st.session_state.get("draft_paper"), st.session_state.get("draft_images")), file_name=f"{st.session_state.get('draft_title')}.pdf", mime="application/pdf")
                except Exception as e: st.error(f"PDF Gen Error: {e}")

    elif teacher_menu == "⚡ Interactive Quiz": render_quiz_engine()
    elif teacher_menu == "💬 AI Chat": render_chat_interface = True 

# --- 3) STUDENT MAIN DASHBOARD (Chat or Quiz) ---
else:
    if app_mode == "⚡ Interactive Quiz": render_quiz_engine()
    else: render_chat_interface = True

# ==========================================
# UNIVERSAL CHAT VIEW (AI Tutor / Teacher Chat)
# ==========================================
if render_chat_interface:
    st.markdown("<div class='big-title'>📚 helix.ai</div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center; opacity: 0.60; font-size: 18px; margin-bottom: 30px;'>Your AI-powered Cambridge (CIE) Tutor for Grade 6-8.</div>", unsafe_allow_html=True)

    for idx, msg in enumerate(st.session_state.get("messages",[])):
        with st.chat_message(msg["role"]):
            disp = msg.get("content") or ""
            disp = re.sub(r"(?i)(?:Here is the )?(?:Analytics|JSON).*?(?:for student)?s?\s*[:-]?\s*", "", disp)
            disp = re.sub(r"===ANALYTICS_START===.*?===ANALYTICS_END===", "", disp, flags=re.IGNORECASE|re.DOTALL)
            disp = re.sub(r"```json\s*\{[^{]*?\"weak_point\".*?\}\s*```", "", disp, flags=re.IGNORECASE|re.DOTALL)
            disp = re.sub(r"\{[^{]*?\"weak_point\".*?\}", "", disp, flags=re.IGNORECASE|re.DOTALL)
            st.markdown(re.sub(r"\[PDF_READY\]", "", disp, flags=re.IGNORECASE).strip())
            
            for img, mod in zip(msg.get("images") or[], msg.get("image_models", ["Unknown"]*10)):
                if img: st.image(img, use_container_width=True, caption=f"✨ Generated by helix.ai ({mod})")
            for b64, mod in zip(msg.get("db_images") or[], msg.get("image_models", ["Unknown"]*10)):
                if b64:
                    try: st.image(base64.b64decode(b64), use_container_width=True, caption=f"✨ Generated by helix.ai ({mod})")
                    except: pass
            
            if msg.get("user_attachment_bytes"):
                mime, name = msg.get("user_attachment_mime", ""), msg.get("user_attachment_name", "File")
                if "image" in mime: st.image(msg["user_attachment_bytes"], use_container_width=True)
                else: st.caption(f"📎 Attached: {name}")
            elif msg.get("user_attachment_b64"):
                try: st.image(base64.b64decode(msg["user_attachment_b64"]), use_container_width=True)
                except: st.caption(f"📎 Attached: {msg.get('user_attachment_name', 'File')}")
            elif msg.get("user_attachment_name"): st.caption(f"📎 Attached: {msg.get('user_attachment_name', 'File')}")

            if msg["role"] == "assistant" and msg.get("is_downloadable"):
                try: st.download_button("📄 Download PDF", data=create_pdf(msg.get("content") or "", msg.get("images") or[base64.b64decode(b) for b in msg.get("db_images", []) if b]), file_name=f"Paper_{idx}.pdf", mime="application/pdf", key=f"dl_{idx}")
                except Exception as e: st.error(f"PDF Error: {e}")

    if chat_input := st.chat_input("Ask Helix...", accept_file=True, file_type=["jpg","png","pdf","txt"]):
        if "textbook_handles" not in st.session_state: st.session_state.textbook_handles = upload_textbooks()
        
        f_bytes, f_mime, f_name = (chat_input.files[0].getvalue() if chat_input.files else None), (chat_input.files[0].type if chat_input.files else None), (chat_input.files[0].name if chat_input.files else None)
        
        if "messages" not in st.session_state: st.session_state.messages =[]
        st.session_state.messages.append({"role": "user", "content": (chat_input.text or "").strip(), "user_attachment_bytes": f_bytes, "user_attachment_mime": f_mime, "user_attachment_name": f_name})
        save_chat_history(); st.rerun()

    if st.session_state.get("messages") and st.session_state.messages[-1]["role"] == "user":
        msg_data = st.session_state.messages[-1]
        with st.chat_message("assistant"):
            think = st.empty(); think.markdown("""<div class="thinking-container"><span class="thinking-text">Thinking</span><div class="thinking-dots"><div class="thinking-dot"></div><div class="thinking-dot"></div><div class="thinking-dot"></div></div></div>""", unsafe_allow_html=True)
            
            try:
                valid_history =[]
                exp_role = "model"
                for m in reversed([m for m in st.session_state.messages[:-1] if not m.get("is_greeting")]):
                    r = "user" if m.get("role") == "user" else "model"
                    txt = m.get("content") or ""
                    if txt.strip() and r == exp_role:
                        valid_history.insert(0, types.Content(role=r, parts=[types.Part.from_text(text=txt)]))
                        exp_role = "user" if exp_role == "model" else "model"
                if valid_history and valid_history[0].role == "model": valid_history.pop(0)

                curr_parts =[]
                student_grade = st.session_state.get("active_grade", user_profile.get("grade", "Grade 6"))
                books = select_relevant_books(" ".join([m.get("content", "") for m in st.session_state.get("messages", [])[-3:]]), st.session_state.get("textbook_handles", {}), student_grade)
                
                if books:
                    for b in books: 
                        curr_parts.append(types.Part.from_text(text=f"--- START OF SOURCE TEXTBOOK: {b.display_name} ---"))
                        curr_parts.append(types.Part.from_uri(file_uri=b.uri, mime_type="application/pdf"))
                        curr_parts.append(types.Part.from_text(text=f"--- END OF SOURCE TEXTBOOK ---"))
                
                if f_bytes := msg_data.get("user_attachment_bytes"):
                    mime = msg_data.get("user_attachment_mime") or guess_mime(msg_data.get("user_attachment_name"))
                    if is_image_mime(mime): curr_parts.append(types.Part.from_bytes(data=f_bytes, mime_type=mime))
                    elif "pdf" in mime:
                        tmp = f"temp_{time.time()}.pdf"; open(tmp, "wb").write(f_bytes); up = client.files.upload_file(tmp)
                        while up.state.name == "PROCESSING": time.sleep(1); up = client.files.get(name=up.name)
                        curr_parts.append(types.Part.from_uri(file_uri=up.uri, mime_type="application/pdf")); os.remove(tmp)

                curr_parts.append(types.Part.from_text(text=f"Context: Student Grade is {student_grade}.\n\nUser Query: {msg_data.get('content')}"))
                
                user_msg_count = sum(1 for m in st.session_state.get("messages",[]) if m["role"] == "user")
                if user_msg_count > 0 and user_msg_count % 6 == 0:
                    curr_parts.append(types.Part.from_text(text="Please analyze the student's previous inputs. If you detect a clear, specific academic weak point, output the hidden ===ANALYTICS_START=== JSON block. If not, do NOT output it."))

                resp = generate_with_retry("gemini-2.5-pro", valid_history +[types.Content(role="user", parts=curr_parts)], types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.3, tools=[{"google_search": {}}]))
                bot_txt = safe_response_text(resp) or "⚠️ *Failed to generate text.*"
                
                match_full = re.search(r"===ANALYTICS_START===(.*?)===ANALYTICS_END===", bot_txt, flags=re.IGNORECASE|re.DOTALL)
                if not match_full: match_full = re.search(r"(?:(?:Here is the )?Analytics.*?:?\s*|```json\s*)?(\{[\s\S]*?\"weak_point\"[\s\S]*?\})(?:\s*```)?", bot_txt, flags=re.IGNORECASE)
                
                if match_full:
                    try:
                        ad = json.loads(match_full.group(1))
                        start_idx = match_full.start()
                        bot_txt = bot_txt[:start_idx].strip()
                        bot_txt = re.sub(r"(?i)(?:Here is the )?(?:Analytics|JSON).*?(?:for student)?s?\s*[:-]?\s*$", "", bot_txt).strip()
                        if is_authenticated and db and ad.get("weak_point"): db.collection("users").document(user_email).collection("analytics").add({"timestamp": time.time(), "source": "chat", **ad})
                    except Exception: pass

                think.empty()
                
                imgs, mods = [],[]
                if v_prompts := re.findall(r"(IMAGE_GEN|PIE_CHART):\s*\[(.*?)\]", bot_txt):
                    with concurrent.futures.ThreadPoolExecutor(5) as exe:
                        for r in exe.map(process_visual_wrapper, v_prompts):
                            if r and r[0]: imgs.append(r[0]); mods.append(r[1])
                
                dl = bool(re.search(r"\[PDF_READY\]", bot_txt, re.IGNORECASE) or (re.search(r"##\s*Mark Scheme", bot_txt, re.IGNORECASE) and re.search(r"\[\d+\]", bot_txt)))
                st.session_state.messages.append({"role": "assistant", "content": bot_txt, "is_downloadable": dl, "images": imgs, "image_models": mods})
                
                if is_authenticated and sum(1 for m in st.session_state.messages if m["role"] == "user") == 1:
                    t = generate_chat_title(client, st.session_state.messages)
                    if t: get_threads_collection().document(st.session_state.get("current_thread_id")).set({"title": t}, merge=True)
                
                save_chat_history(); st.rerun()
                
            except Exception as e: think.empty(); st.error(f"Error: {e}")
