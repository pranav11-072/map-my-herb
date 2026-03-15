import os
import qrcode
import io
import base64
import datetime
import hashlib
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_change_this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///herb_chain.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(64), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    action = db.Column(db.String(100), nullable=False)
    data = db.Column(db.Text, nullable=False)
    previous_hash = db.Column(db.String(64))
    hash = db.Column(db.String(64), unique=True)

    def __repr__(self):
        return f"Block {self.id} for Batch {self.batch_id}"

    def compute_hash(self):
        block_string = f"{self.batch_id}{self.timestamp}{self.action}{self.data}{self.previous_hash}"
        return hashlib.sha256(block_string.encode()).hexdigest()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_batch', methods=['GET', 'POST'])
def add_batch():
    if request.method == 'POST':
        herb_name = request.form['herb_name']
        location = request.form['location']
        notes = request.form['notes']

        batch_id_str = f"{herb_name}{datetime.datetime.utcnow()}"
        batch_id = hashlib.md5(batch_id_str.encode()).hexdigest()[:10]

        new_block = Block(
            batch_id=batch_id,
            action="HARVESTED",
            data=f"Herb: {herb_name}, Location: {location}, Notes: {notes}",
            previous_hash="0"
        )
        
        new_block.hash = new_block.compute_hash()
        
        db.session.add(new_block)
        db.session.commit()

        flash(f'New herb batch {batch_id} created successfully!', 'success')
        return redirect(url_for('show_qr', batch_id=batch_id))

    return render_template('add_batch.html')

@app.route('/update_batch/<batch_id>', methods=['GET', 'POST'])
def update_batch(batch_id):
    
    last_block = Block.query.filter_by(batch_id=batch_id).order_by(Block.timestamp.desc()).first()

    if not last_block:
        flash(f'Batch ID {batch_id} not found.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        action = request.form['action']
        details = request.form['details']

        new_block = Block(
            batch_id=batch_id,
            action=action.upper(),
            data=details,
            previous_hash=last_block.hash
        )
        
        new_block.hash = new_block.compute_hash()
        
        db.session.add(new_block)
        db.session.commit()

        flash(f'Batch {batch_id} updated with action: {action}', 'success')
        return redirect(url_for('trace', batch_id=batch_id))

    return render_template('update_batch.html', batch_id=batch_id, last_action=last_block.action)


@app.route('/trace', methods=['GET'])
def trace_form():
    return render_template('trace_form.html')


@app.route('/trace/<batch_id>')
def trace(batch_id):
    
    blocks = Block.query.filter_by(batch_id=batch_id).order_by(Block.timestamp.asc()).all()
    
    if not blocks:
        flash(f'Batch ID {batch_id} not found.', 'danger')
        return redirect(url_for('trace_form'))
        
    return render_template('trace.html', blocks=blocks, batch_id=batch_id)

@app.route('/qr/<batch_id>')
def show_qr(batch_id):
    
    trace_url = url_for('trace', batch_id=batch_id, _external=True)
    
    img = qrcode.make(trace_url)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    
    img_data = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return render_template('qr_code.html', batch_id=batch_id, trace_url=trace_url, img_data=img_data)


@app.cli.command('init-db')
def init_db_command():
    db.create_all()
    print('Initialized the database.')

if __name__ == '__main__':
    if not os.path.exists('herb_chain.db'):
        with app.app_context():
            db.create_all()
            print("Database created!")
            
    app.run(debug=True)
