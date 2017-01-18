import scrypt
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User

class ScryptLoginBackend(object):
    """
    All user passwords are ran through scrypt to protect user's money.
    This backend preforms that scrypt processing so admins can login to the
    admin section with the same password they use for the wallet.
    """

    def authenticate(self, username=None, password=None):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None

        if check_password(password, user.password):
            return user

        # try running password through same scrypt params as front end.
        encoded_password = scrypt.hash(str(password), str(username), 16384, 8, 1).encode('hex')
        if check_password(encoded_password, user.password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
