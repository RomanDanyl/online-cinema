import os

from database.models.base import Base
from database.models.accounts import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserProfileModel,
)
from database.models.movies import (
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
    MovieModel,
    MovieRatingModel,
    MovieCommentModel,
    MovieCommentLikeModel,
    MovieFavoriteModel,
    MovieReactionModel,
    UserReactionsEnum,
)
from database.models.commerce import (
    CartModel,
    CartItemModel,
    OrderModel,
    OrderItemModel,
    OrderStatusEnum,
    PaymentModel,
    PaymentItemModel,
    PaymentStatusEnum,
)
from database.session_sqlite import reset_sqlite_database as reset_database
from database.validators import accounts as accounts_validators

environment = os.getenv("ENVIRONMENT", "developing")

if environment == "testing":
    from database.session_sqlite import (
        get_sqlite_db_contextmanager as get_db_contextmanager,
        get_sqlite_db as get_db,
    )
else:
    from database.session_postgresql import (
        get_postgresql_db_contextmanager as get_db_contextmanager,
        get_postgresql_db as get_db,
    )
