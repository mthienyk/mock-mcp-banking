from datetime import datetime
import secrets
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)

    # Relationships
    votes_cast = relationship(
        "TaxVote", foreign_keys="TaxVote.voter_id", back_populates="voter", cascade="all, delete-orphan"
    )
    votes_received = relationship(
        "TaxVote", foreign_keys="TaxVote.target_id", back_populates="target", cascade="all, delete-orphan"
    )

    @staticmethod
    def generate_token(name: str) -> str:
        """Generates a secure, readable API token for the user."""
        clean_name = "".join(c for c in name.lower() if c.isalnum())
        random_suffix = secrets.token_hex(4)
        return f"bank_{clean_name}_{random_suffix}"


class TaxVote(Base):
    __tablename__ = "tax_votes"

    id = Column(Integer, primary_key=True, index=True)
    voter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    voter = relationship("User", foreign_keys=[voter_id], back_populates="votes_cast")
    target = relationship("User", foreign_keys=[target_id], back_populates="votes_received")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)  # 'withdrawal', 'transfer', 'taxation', 'redistribution'
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships for easy auditing
    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])


class CommonPot(Base):
    __tablename__ = "common_pot"

    id = Column(Integer, primary_key=True, index=True)
    balance = Column(Float, default=1000000.0, nullable=False)


class GameMeta(Base):
    """Singleton: session (lobby → active → frozen) pilotée par l'animateur."""

    __tablename__ = "game_meta"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    session_started_at = Column(DateTime, nullable=True)
    phase = Column(String, default="discovery", nullable=False)
    frozen_at = Column(DateTime, nullable=True)
    frozen_reason = Column(String, nullable=True)


class UserGameState(Base):
    """État de jeu par élève (slots de retrait, fenêtre anti-spam)."""

    __tablename__ = "user_game_state"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    withdrawal_slots = Column(Integer, default=0, nullable=False)
    last_slot_unlock_at = Column(DateTime, nullable=True)
    withdraw_window_start = Column(DateTime, nullable=True)
    withdraw_count_in_window = Column(Integer, default=0, nullable=False)
    last_spy_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="game_state")


class AllianceProposal(Base):
    __tablename__ = "alliance_proposals"

    id = Column(Integer, primary_key=True, index=True)
    proposer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    proposer = relationship("User", foreign_keys=[proposer_id])
    target = relationship("User", foreign_keys=[target_id])


class Alliance(Base):
    __tablename__ = "alliances"

    id = Column(Integer, primary_key=True, index=True)
    user_a_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user_b_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    formed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user_a = relationship("User", foreign_keys=[user_a_id])
    user_b = relationship("User", foreign_keys=[user_b_id])


class BalanceSpy(Base):
    """Dernière espionnage par (spy, target) pour cooldown."""

    __tablename__ = "balance_spies"

    id = Column(Integer, primary_key=True, index=True)
    spy_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    spied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
