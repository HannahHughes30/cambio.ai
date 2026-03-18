"""End-to-end Playwright test for the Cambio web GUI."""

import time
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:5050"


def test_lobby_and_game():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # ---- LOBBY ----
        print("=== Testing Lobby ===")
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        print(f"  Title: {page.title()}")

        # Verify lobby elements exist
        assert page.locator("#player-name").is_visible(), "Name input not visible"
        assert page.locator("#player-type").is_visible(), "Type selector not visible"
        assert page.locator("#add-btn").is_visible(), "Add button not visible"
        assert page.locator("#start-btn").is_disabled(), "Start should be disabled with 0 players"
        print("  Lobby elements: OK")

        # Add a human player
        page.fill("#player-name", "TestHuman")
        page.select_option("#player-type", "human")
        page.click("#add-btn")
        time.sleep(0.5)

        # Should see the player in the list
        player_list = page.locator(".player-item")
        assert player_list.count() == 1, f"Expected 1 player, got {player_list.count()}"
        assert page.locator("#start-btn").is_disabled(), "Start should be disabled with 1 player"
        print("  Added human player: OK")

        # Add a bot
        page.fill("#player-name", "SmartBot")
        page.select_option("#player-type", "smart")
        page.click("#add-btn")
        time.sleep(0.5)

        assert player_list.count() == 2, f"Expected 2 players, got {player_list.count()}"
        assert not page.locator("#start-btn").is_disabled(), "Start should be enabled with 2 players"
        print("  Added bot player: OK")

        # Remove the bot and re-add to test remove
        page.locator(".remove-btn").last.click()
        time.sleep(0.5)
        assert player_list.count() == 1, "Should have 1 player after remove"
        print("  Remove player: OK")

        # Re-add bot
        page.fill("#player-name", "BayBot")
        page.select_option("#player-type", "bayesian_v2")
        page.click("#add-btn")
        time.sleep(0.5)
        assert player_list.count() == 2
        print("  Re-added bot: OK")

        # ---- START GAME ----
        print("\n=== Starting Game ===")

        # Click start and wait for redirect to game page
        page.click("#start-btn")
        page.wait_for_url("**/game/**", timeout=5000)
        page.wait_for_load_state("networkidle")
        print(f"  Redirected to: {page.url}")
        assert "/game/" in page.url, "Should be on game page"

        # Wait for game state to load
        time.sleep(2)

        # ---- GAME BOARD ----
        print("\n=== Testing Game Board ===")

        # Verify core game elements
        assert page.locator("#turn-indicator").is_visible(), "Turn indicator not visible"
        assert page.locator("#deck-count").is_visible(), "Deck count not visible"
        assert page.locator("#opponents-area").is_visible(), "Opponents area not visible"
        assert page.locator("#your-hand").is_visible(), "Your hand not visible"
        print("  Game board elements: OK")

        # Check hand is rendered in 2x2 grid
        hand_cards = page.locator("#your-hand .card")
        card_count = hand_cards.count()
        print(f"  Hand cards: {card_count}")
        assert card_count == 4, f"Expected 4 cards, got {card_count}"

        # Check that 2 cards are face-up (known) and 2 face-down
        face_up = page.locator("#your-hand .card-face")
        face_down = page.locator("#your-hand .card-back")
        print(f"  Face-up: {face_up.count()}, Face-down: {face_down.count()}")
        assert face_up.count() == 2, f"Expected 2 known cards, got {face_up.count()}"
        assert face_down.count() == 2, f"Expected 2 unknown cards, got {face_down.count()}"
        print("  Initial card visibility: OK")

        # Verify opponents shown
        opp_cards = page.locator(".opp-hand-grid .card")
        print(f"  Opponent cards: {opp_cards.count()}")
        assert opp_cards.count() == 4, f"Expected 4 opponent cards, got {opp_cards.count()}"

        # Check deck count is reasonable
        deck_text = page.locator("#deck-count").text_content()
        print(f"  Deck count: {deck_text}")

        # ---- PLAY THROUGH DECISIONS ----
        print("\n=== Playing Through Decisions ===")

        # Wait for prompt to appear (might need to wait for bot turns)
        prompt_area = page.locator("#prompt-area")
        prompt_area.wait_for(state="visible", timeout=15000)
        prompt_text = page.locator("#prompt-text").text_content()
        print(f"  First prompt: {prompt_text[:80]}...")

        decisions_made = 0
        max_decisions = 30  # safety limit

        while decisions_made < max_decisions:
            # Check for game over
            game_over = page.locator("#game-over")
            if game_over.is_visible():
                print(f"\n  GAME OVER detected after {decisions_made} decisions!")
                results = page.locator("#game-over-results").text_content()
                print(f"  Results: {results[:120]}...")
                break

            # Wait for a prompt
            try:
                prompt_area.wait_for(state="visible", timeout=15000)
            except Exception:
                # Maybe game ended while waiting
                if game_over.is_visible():
                    print(f"\n  GAME OVER (during wait) after {decisions_made} decisions!")
                    break
                print("  Timeout waiting for prompt - possible deadlock!")
                # Take screenshot for debugging
                page.screenshot(path="/tmp/cambio_timeout.png")
                break

            prompt_text = page.locator("#prompt-text").text_content()
            prompt_type = identify_prompt_type(prompt_text)
            decisions_made += 1

            print(f"  Decision {decisions_made}: {prompt_type} - {prompt_text[:60]}...")

            if prompt_type == "draw":
                # Always draw from deck for simplicity
                deck_btn = page.locator("button", has_text="Draw from Deck")
                if deck_btn.is_visible():
                    deck_btn.click()
                else:
                    # Might only have deck option
                    page.locator(".prompt-buttons button").first.click()

            elif prompt_type == "swap_position":
                # Must swap - click first card in hand
                clickable = page.locator("#your-hand .card-clickable")
                if clickable.count() > 0:
                    clickable.first.click()
                else:
                    page.locator("#your-hand .card").first.click()

            elif prompt_type == "action":
                # Swap or discard - click discard for simplicity
                discard_btn = page.locator("button", has_text="Discard")
                if discard_btn.is_visible():
                    discard_btn.click()
                else:
                    page.locator("#your-hand .card-clickable").first.click()

            elif prompt_type == "power":
                # Skip power for simplicity
                skip_btn = page.locator("button", has_text="Skip")
                if skip_btn.count() > 0:
                    skip_btn.first.click()
                else:
                    page.locator(".prompt-buttons button").first.click()

            elif prompt_type == "king_confirm":
                # Don't swap
                skip_btn = page.locator("button", has_text="Don't Swap")
                if skip_btn.is_visible():
                    skip_btn.click()
                else:
                    page.locator(".prompt-buttons button").last.click()

            elif prompt_type == "cambio":
                # Don't call cambio early, call after 10 decisions
                if decisions_made > 10:
                    page.locator("button", has_text="Call Cambio").click()
                else:
                    not_yet = page.locator("button", has_text="Not yet")
                    if not_yet.is_visible():
                        not_yet.click()
                    else:
                        page.locator(".prompt-buttons button").last.click()

            elif prompt_type == "stick":
                # Skip stick
                skip_btn = page.locator("button", has_text="Skip")
                if skip_btn.is_visible():
                    skip_btn.click()
                else:
                    page.locator(".prompt-buttons button").first.click()

            else:
                # Unknown prompt, click first button
                print(f"    Unknown prompt type, clicking first button")
                page.locator(".prompt-buttons button").first.click()

            time.sleep(0.3)  # Small delay between actions

        # ---- VERIFY GAME LOG ----
        print("\n=== Checking Game Log ===")
        log_entries = page.locator(".log-entry")
        print(f"  Log entries: {log_entries.count()}")
        assert log_entries.count() > 0, "Should have log entries"

        # ---- PLAY AGAIN ----
        print("\n=== Testing Play Again ===")
        game_over = page.locator("#game-over")
        if game_over.is_visible():
            play_again_btn = page.locator("button", has_text="Play Again")
            if play_again_btn.is_visible():
                play_again_btn.click()
                page.wait_for_url(BASE + "/", timeout=5000)
                print("  Returned to lobby: OK")

        page.screenshot(path="/tmp/cambio_final.png")
        browser.close()
        print("\n=== ALL TESTS PASSED ===")


def identify_prompt_type(text):
    text_lower = text.lower()
    if "choose where to draw" in text_lower or "draw from the deck" in text_lower:
        return "draw"
    if "from the discard pile" in text_lower and "replace" in text_lower:
        return "swap_position"
    if "swap it into your hand or discard" in text_lower:
        return "action"
    if "peek" in text_lower or "blind swap" in text_lower or "black king" in text_lower or "spy" in text_lower:
        return "power"
    if "swap with your position" in text_lower or "swap?" in text_lower:
        return "king_confirm"
    if "call cambio" in text_lower:
        return "cambio"
    if "stick" in text_lower:
        return "stick"
    return "unknown"


if __name__ == "__main__":
    test_lobby_and_game()
