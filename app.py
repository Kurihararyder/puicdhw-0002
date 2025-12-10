from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random
import string
import json
from datetime import datetime
from openai import OpenAI  # 匯入 OpenAI 套件

app = Flask(__name__)

# --- 設定 ---
app.config['SECRET_KEY'] = 'your_very_secret_key_here' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 資料庫模型 (Models) ---
enrollments = db.Table('enrollments',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('classroom_id', db.Integer, db.ForeignKey('classroom.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user') 
    taught_classes = db.relationship('Classroom', backref='teacher', lazy=True)
    enrolled_classes = db.relationship('Classroom', secondary=enrollments, lazy='subquery',
        backref=db.backref('students', lazy=True))
    logs = db.relationship('LearningLog', backref='user', lazy=True, order_by="desc(LearningLog.timestamp)")

class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    assignments = db.relationship('Assignment', backref='classroom', lazy=True)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

class LearningLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_type = db.Column(db.String(50))
    score = db.Column(db.Integer, default=0)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.now)

# --- 設定 OpenAI Client ---
# ⚠️ 請在此填入您的 OpenAI API Key (sk- 開頭的那串)
OPENAI_API_KEY = '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'

client = OpenAI(api_key=OPENAI_API_KEY)

# --- 核心路由 ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            else:
                return redirect(url_for('user_home'))
        else:
            flash('帳號或密碼錯誤')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 學生功能 ---
@app.route('/home')
def user_home():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('home.html', user=user)

@app.route('/join_class', methods=['POST'])
def join_class():
    if 'user_id' not in session: return redirect(url_for('login'))
    code = request.form.get('class_code').strip()
    classroom = Classroom.query.filter_by(code=code).first()
    user = User.query.get(session['user_id'])
    
    if not classroom:
        flash('❌ 找不到此班級代碼')
    elif classroom in user.enrolled_classes:
        flash('⚠️ 你已經加入過這個班級了')
    else:
        user.enrolled_classes.append(classroom)
        db.session.commit()
        flash(f'✅ 成功加入班級：{classroom.name}')
    return redirect(url_for('user_home'))

@app.route('/student/class/<int:class_id>')
def student_class_view(class_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    classroom = Classroom.query.get_or_404(class_id)
    return render_template('student_class.html', classroom=classroom)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    logs = LearningLog.query.filter_by(user_id=user.id).order_by(LearningLog.timestamp.desc()).limit(10).all()
    return render_template('dashboard.html', name=user.username, logs=logs, current_user=user)

@app.route('/quiz')
def quiz_page():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('quiz.html', current_user=user)

@app.route('/chat')
def chat_scenario():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('chat.html', current_user=user)


# --- AI API (OpenAI 出題邏輯) ---

@app.route('/api/quiz/generate', methods=['POST'])
def api_quiz_generate():
    data = request.json
    level = data.get('level', 'N3')
    
    # 使用 gpt-4o-mini (便宜、快速、支援 JSON Mode)
    model_id = "gpt-4o-mini"

    # 設定系統提示詞，明確要求 JSON 格式
    system_msg = "你是一位 JLPT 日檢出題老師。請務必以 JSON 格式回傳題目。"
    
    # 🔥 重要：這裡的 Prompt 已經修正，要求 answer 必須是完整文字
    user_msg = f"""
    請出一個 {level} 等級的「單字」或「文法」四選一題目。
    
    【重要規則】
    1. `answer` 的內容**必須完全等於** `options` 陣列中的某一個選項文字。
    2. **絕對不要**使用 A, B, C, D 或 1, 2, 3, 4 作為答案代號。
    3. JSON 必須包含：question, options, answer, explanation。

    JSON 範例：
    {{
        "question": "「猫」的日文讀音是什麼？",
        "options": ["ねこ", "いぬ", "とり", "さかな"],
        "answer": "ねこ",
        "explanation": "貓的日文發音是 Neko (ねこ)。"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            response_format={"type": "json_object"}, # 🔥 強制 JSON 輸出
            temperature=0.7
        )
        
        raw_content = response.choices[0].message.content
        print(f"[Debug] AI Response: {raw_content}") 

        quiz_data = json.loads(raw_content)
        return jsonify(quiz_data)

    except Exception as e:
        print(f"[Error] API Failed: {repr(e)}")
        # 處理常見的額度不足錯誤
        if "quota" in str(e).lower():
            return jsonify({'error': 'OpenAI 額度不足 (Quota Exceeded)，請檢查帳單。'}), 500
        return jsonify({'error': f'AI Error: {str(e)}'}), 500

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json
    user_msg = data.get('message')
    history = data.get('history', [])
    
    # 建構訊息列表 (OpenAI 格式)
    messages = [
        {"role": "system", "content": "你現在是日本便利商店的店員，請用日文與顧客對話。請簡短回應(20字以內)。"}
    ]
    
    # 放入歷史紀錄
    for msg in history[-5:]:
        messages.append(msg)
        
    messages.append({"role": "user", "content": user_msg})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        reply = response.choices[0].message.content
        return jsonify({'reply': reply})
    except Exception as e:
        print(f"[Error] Chat Failed: {repr(e)}")
        return jsonify({'reply': 'すみません、エラーが発生しました。'})

@app.route('/api/quiz/save', methods=['POST'])
def api_quiz_save():
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    new_log = LearningLog(
        user_id=session['user_id'],
        activity_type=f"{data.get('level')} Quiz",
        score=data.get('score', 0),
        details="AI Quiz"
    )
    db.session.add(new_log)
    db.session.commit()
    return jsonify({'success': True})

# --- 導師與管理員路由 ---

@app.route('/teacher')
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    teacher_id = session['user_id']
    my_classrooms = Classroom.query.filter_by(teacher_id=teacher_id).all()
    return render_template('teacher.html', classrooms=my_classrooms)

@app.route('/create_class', methods=['POST'])
def create_class():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    class_name = request.form.get('class_name')
    new_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    new_class = Classroom(name=class_name, teacher_id=session['user_id'], code=new_code)
    db.session.add(new_class)
    db.session.commit()
    flash(f'Class Created! Code: {new_code}')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/class/<int:class_id>')
def class_dashboard(class_id):
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    classroom = Classroom.query.get_or_404(class_id)
    return render_template('class_dashboard.html', classroom=classroom)

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/admin/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    user_to_edit = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user_to_edit.username = request.form['username']
        user_to_edit.role = request.form['role']
        if request.form['password']:
            user_to_edit.password_hash = generate_password_hash(request.form['password'])
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_user.html', user=user_to_edit)

@app.route('/admin/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'admin': return "Permission Denied", 403
    user_to_delete = User.query.get_or_404(user_id)
    db.session.delete(user_to_delete)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

def create_initial_data():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password_hash=generate_password_hash('admin123'), role='admin'))
            db.session.add(User(username='teacher1', password_hash=generate_password_hash('teach123'), role='teacher'))
            db.session.add(User(username='student1', password_hash=generate_password_hash('stu123'), role='user'))
            db.session.add(User(username='student2', password_hash=generate_password_hash('stu123'), role='user'))
            db.session.commit()
            print("Init DB Done!")

if __name__ == '__main__':
    create_initial_data()
    app.run(debug=True)