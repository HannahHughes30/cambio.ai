"""GUI for playing Cambio against an opponent."""
import tkinter as tk
from tkinter import messagebox

from game import CambioGame, Player
from agents.base_agent import BaseAgent

AGENT_REGISTRY = {
    'base': BaseAgent
}

"""Not yet complete. Will hopefully have most actions and a agent to play against.
    It may or may not error. 
Current state: Shows idea of what the cambio GUI may look like. 
                Can peek own cards, swap with opponent, and an incomplete cambio call. 
                Still need to implement draw card, power actions, working agent, and a proper cambio call."""
class CambioGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Cambio")
        self.p1 = Player("Player")
        self.p2 = AGENT_REGISTRY['base']("Opponent")
        self.selected_card_i = None
        self.selected_opponent_card_i = None
        self.game = CambioGame([self.p1, self.p2])
        self.game.deal()
        self.player_hand = [card for card in self.p1.known.values()] + ["?" for _ in range(4 - len(self.p1.known))]
        self.opponent_hand = ["?" for _ in range(4)]

        self.build_layout()
        self.update_cards()

    def build_layout(self):

        """Opponent label"""
        tk.Label(self.root, text="Opponent", font=("Arial",16)).pack(pady=5)

        self.opponent_frame = tk.Frame(self.root)
        self.opponent_frame.pack(pady=5)

        """player actions"""
        middle = tk.Frame(self.root)
        middle.pack(pady=15)

        tk.Button(middle, text="Draw Card", command=self.draw_card).grid(row=0, column=0, padx=20)
        tk.Button(middle, text="Peek", command=self.peek).grid(row=0, column=1, padx=20)
        tk.Button(middle, text="CALL CAMBIO", command=self.call_cambio).grid(row=0, column=3, padx=20)

        """Player label"""
        tk.Label(self.root, text="Your Cards", font=("Arial",16)).pack(pady=5)

        self.player_frame = tk.Frame(self.root)
        self.player_frame.pack(pady=5)

        self.log = tk.Text(self.root, height=6, width=45)
        self.log.pack(pady=10)

    def update_cards(self):
        for w in self.player_frame.winfo_children():
            w.destroy()
        for w in self.opponent_frame.winfo_children():
            w.destroy()

        for i, card in enumerate(self.opponent_hand):
            btn = tk.Button(self.opponent_frame,
                            text=card,
                            font=("Arial",30),
                            command=lambda i=i: self.opponent_card_clicked(i))
            btn.pack(side="left", padx=10)

        for i, card in enumerate(self.p1.hand):
            if i in self.p1.known:
                text = self.card_to_text(card)
            else:
                text = "?"

            btn = tk.Button(self.player_frame,
                            text=text,
                            font=("Arial",30),
                            command=lambda i=i: self.card_clicked(i))
            btn.pack(side="left", padx=10)

    def card_to_text(self, card):
        if card.rank == "Joker":
            return "Joker"
        suit_symbols = {
            "Hearts": "♥",
            "Diamonds": "♦",
            "Clubs": "♣",
            "Spades": "♠",
        }
        return f"{card.rank}{suit_symbols[card.suit]}"

    def card_clicked(self, index):
        self.selected_card_i = index
        self.log.insert(tk.END, f"Selected card {index+1}\n")

    def peek(self):
        if self.selected_card_i is not None:
            self.game.peek(self.p1, self.selected_card_i)
            card = self.p1.hand[self.selected_card_i]
            self.p1.known[self.selected_card_i] = card
            self.player_hand[self.selected_card_i] = card
            self.log.insert(tk.END, f"Peeked at card {self.selected_card_i+1}: {card}\n")
            self.update_cards()
        else:
            self.log.insert(tk.END, "Select one of your own cards.\n")

    # Swap when we click our card first and then opponent's card
    def opponent_card_clicked(self, index):
        if self.selected_card_i is None:
            self.log.insert(tk.END, "Select your card first!\n")
            return

        self.game.swap(self.p1, self.p2, self.selected_card_i, index)

        self.log.insert(tk.END, f"Swapped your card {self.selected_card_i+1} with opponent card {index+1}\n")

        self.update_cards()
        self.selected_card_i = None

    def draw_card(self):
        pass

    def call_cambio(self):
        messagebox.showinfo("Cambio!", "Cambio called! Round ending soon...")
        self.log.insert(tk.END, "You called CAMBIO!\n")
        self.log.insert(tk.END, "Opponent's cards were: " + ", ".join(self.card_to_text(c) for c in self.p2.hand) + "\n")
        self.log.insert(tk.END, f"Scores - You: {self.game.calculate_score(self.p1)}, Opponent: {self.game.calculate_score(self.p2)}\n")


if __name__ == "__main__":
    root = tk.Tk()
    app = CambioGUI(root)
    root.mainloop()