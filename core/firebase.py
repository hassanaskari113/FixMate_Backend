import os

import firebase_admin
from firebase_admin import auth, credentials

folder = "firebase"
file_name = "serviceAccountKey.json"
path = os.path.join(folder, file_name)

cred = credentials.Certificate(path)
firebase_admin.initialize_app(cred)


def verify_token(id_token):
    id_info = auth.verify_id_token(id_token=id_token)

    return id_info
