from abc import ABC, abstractmethod


class EmailSenderInterface(ABC):

    @abstractmethod
    async def send_activation_email(self, email: str, activation_link: str) -> None:
        """
        Asynchronously send an account activation email.

        Args:
            email (str): The recipient's email address.
            activation_link (str): The activation link to include in the email.
        """
        pass

    @abstractmethod
    async def send_activation_complete_email(self, email: str, login_link: str) -> None:
        """
        Asynchronously send an email confirming that the account has been activated.

        Args:
            email (str): The recipient's email address.
            login_link (str): The login link to include in the email.
        """
        pass

    @abstractmethod
    async def send_password_reset_email(self, email: str, reset_link: str) -> None:
        """
        Asynchronously send a password reset request email.

        Args:
            email (str): The recipient's email address.
            reset_link (str): The password reset link to include in the email.
        """
        pass

    @abstractmethod
    async def send_password_reset_complete_email(
        self, email: str, login_link: str
    ) -> None:
        """
        Asynchronously send an email confirming that the password has been reset.

        Args:
            email (str): The recipient's email address.
            login_link (str): The login link to include in the email.
        """
        pass

    @abstractmethod
    async def send_comment_notification(
        self,
        email: str,
        subject: str,
        intro_message: str,
        movie_name: str,
        comment_text: str,
    ) -> None:
        """
        Send a notification related to movie comments.

        Args:
            email: Recipient email address.
            subject: Email subject.
            intro_message: Introductory text describing the interaction.
            movie_name: Name of the related movie.
            comment_text: Text of the related comment.
        """
        pass

    @abstractmethod
    async def send_payment_confirmation_email(
        self,
        email: str,
        order_id: int,
        amount: str,
    ) -> None:
        """
        Send a confirmation email about a successful payment.

        Args:
            email: Recipient email address.
            order_id: Paid order identifier.
            amount: Paid amount formatted as string.
        """
        pass

    @abstractmethod
    async def send_movie_deletion_blocked_notification(
            self,
            email: str,
            movie_name: str,
            cart_count: int,
            requested_by: str,
    ) -> None:
        """
        Send a notification to moderators when movie deletion is blocked.

        Args:
            email: Recipient email address.
            movie_name: Name of the movie that could not be deleted.
            cart_count: Number of cart items that contain the movie.
            requested_by: Email of the admin who attempted the deletion.
        """
        pass
