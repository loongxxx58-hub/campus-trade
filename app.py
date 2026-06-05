from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'xiao_shi_tao_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///campus.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(200), default='default_avatar.png')
    created_at = db.Column(db.DateTime, default=datetime.now)
    products = db.relationship('Product', backref='seller', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), default='default.jpg')
    status = db.Column(db.String(20), default='在售')
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.relationship('Message', backref='product', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    author = db.relationship('User', backref='messages')

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    sort = request.args.get('sort', 'new')
    query = Product.query.filter_by(status='在售')
    if search:
        query = query.filter(Product.name.contains(search) | Product.description.contains(search))
    if category:
        query = query.filter_by(category=category)
    if sort == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort == 'views':
        query = query.order_by(Product.views.desc())
    else:
        query = query.order_by(Product.created_at.desc())
    products = query.all()
    categories = ['教材书籍', '电子产品', '生活用品', '运动器材', '服装鞋帽', '其他']
    return render_template('index.html', products=products, categories=categories, search=search, current_category=category, sort=sort)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('用户名已存在！', 'danger')
            return redirect(url_for('register'))
        user = User(username=username, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash('注册成功，请登录！', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('登录成功！', 'success')
            return redirect(url_for('index'))
        flash('用户名或密码错误！', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/publish', methods=['GET', 'POST'])
@login_required
def publish():
    if request.method == 'POST':
        image_filename = 'default.jpg'
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = str(int(datetime.now().timestamp()))
                filename = timestamp + '_' + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        product = Product(
            name=request.form['name'],
            category=request.form['category'],
            price=float(request.form['price']),
            description=request.form['description'],
            image=image_filename,
            user_id=current_user.id
        )
        db.session.add(product)
        db.session.commit()
        flash('商品发布成功！', 'success')
        return redirect(url_for('index'))
    return render_template('publish.html')

@app.route('/product/<int:id>', methods=['GET', 'POST'])
def product_detail(id):
    product = Product.query.get_or_404(id)
    product.views += 1
    db.session.commit()
    is_favorited = False
    if current_user.is_authenticated:
        is_favorited = Favorite.query.filter_by(user_id=current_user.id, product_id=id).first() is not None
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('请先登录再留言！', 'danger')
            return redirect(url_for('login'))
        msg = Message(content=request.form['content'], user_id=current_user.id, product_id=id)
        db.session.add(msg)
        db.session.commit()
        flash('留言成功！', 'success')
    messages = Message.query.filter_by(product_id=id).order_by(Message.created_at.desc()).all()
    return render_template('product_detail.html', product=product, messages=messages, is_favorited=is_favorited)

@app.route('/favorite/<int:id>')
@login_required
def toggle_favorite(id):
    fav = Favorite.query.filter_by(user_id=current_user.id, product_id=id).first()
    if fav:
        db.session.delete(fav)
        flash('已取消收藏', 'info')
    else:
        db.session.add(Favorite(user_id=current_user.id, product_id=id))
        flash('收藏成功！', 'success')
    db.session.commit()
    return redirect(url_for('product_detail', id=id))

@app.route('/my_favorites')
@login_required
def my_favorites():
    favs = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).all()
    products = [Product.query.get(f.product_id) for f in favs]
    return render_template('my_favorites.html', products=products)

@app.route('/my_products')
@login_required
def my_products():
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.created_at.desc()).all()
    return render_template('my_products.html', products=products)

@app.route('/delete_product/<int:id>')
@login_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    if product.user_id != current_user.id:
        flash('无权操作！', 'danger')
        return redirect(url_for('my_products'))
    db.session.delete(product)
    db.session.commit()
    flash('商品已删除！', 'success')
    return redirect(url_for('my_products'))

@app.route('/sold/<int:id>')
@login_required
def mark_sold(id):
    product = Product.query.get_or_404(id)
    if product.user_id == current_user.id:
        product.status = '已售出'
        db.session.commit()
        flash('已标记为售出！', 'success')
    return redirect(url_for('my_products'))

@app.route('/profile/<int:id>')
def profile(id):
    user = User.query.get_or_404(id)
    products = Product.query.filter_by(user_id=id, status='在售').all()
    return render_template('profile.html', user=user, products=products)
class WantToBuy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    budget = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='求购中')
    created_at = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    buyer = db.relationship('User', backref='wants')

@app.route('/want')
def want_list():
    wants = WantToBuy.query.order_by(WantToBuy.created_at.desc()).all()
    return render_template('want_list.html', wants=wants)

@app.route('/want/publish', methods=['GET', 'POST'])
@login_required
def want_publish():
    if request.method == 'POST':
        want = WantToBuy(
            title=request.form['title'],
            description=request.form['description'],
            budget=float(request.form['budget']) if request.form['budget'] else None,
            user_id=current_user.id
        )
        db.session.add(want)
        db.session.commit()
        flash('求购信息发布成功！', 'success')
        return redirect(url_for('want_list'))
    return render_template('want_publish.html')

@app.route('/want/delete/<int:id>')
@login_required
def want_delete(id):
    want = WantToBuy.query.get_or_404(id)
    if want.user_id == current_user.id:
        db.session.delete(want)
        db.session.commit()
        flash('已删除求购信息', 'success')
    return redirect(url_for('want_list'))
# 管理员装饰器
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.username != 'admin':
            flash('需要管理员权限！', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@login_required
@admin_required
def admin_index():
    total_users = User.query.count()
    total_products = Product.query.count()
    total_messages = Message.query.count()
    total_wants = WantToBuy.query.count()
    recent_products = Product.query.order_by(Product.created_at.desc()).limit(5).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    return render_template('admin/index.html',
        total_users=total_users,
        total_products=total_products,
        total_messages=total_messages,
        total_wants=total_wants,
        recent_products=recent_products,
        recent_users=recent_users)

@app.route('/admin/products')
@login_required
@admin_required
def admin_products():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/products.html', products=products)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/delete_product/<int:id>')
@login_required
@admin_required
def admin_delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('商品已删除！', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/delete_user/<int:id>')
@login_required
@admin_required
def admin_delete_user(id):
    user = User.query.get_or_404(id)
    if user.username == 'admin':
        flash('不能删除管理员账号！', 'danger')
        return redirect(url_for('admin_users'))
    db.session.delete(user)
    db.session.commit()
    flash('用户已删除！', 'success')
    return redirect(url_for('admin_users'))
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs('static/uploads', exist_ok=True)
    app.run(debug=True)