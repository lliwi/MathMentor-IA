"""
MathMentor IA - Main Application Entry Point
"""
import sys
from app import create_app

# Disable stdout buffering for Docker logs
sys.stdout = sys.stderr

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
