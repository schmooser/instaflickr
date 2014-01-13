#gunicorn --daemon --bind=0.0.0.0:5000 instaflickr:app
#gunicorn --daemon --bind=127.0.0.1:5000 --log-level debug --log-file instaflickr.log instaflickr:app
gunicorn --daemon --bind=127.0.0.1:5000 --log-level debug --log-file gunicorn.log instaflickr:app
