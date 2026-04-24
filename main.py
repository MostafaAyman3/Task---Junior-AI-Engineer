import os
import sys
from data.store import DataStore
from agent.agent import Agent

def main():
    """
    This is the main entry point of the application. 
    When you type 'python main.py' in the terminal, this function is executed first.
    It prepares the data, starts the AI agent, and sets up the chat loop so you can talk to the bot.
    """
    print("Initializing DataStore...")
    
    # 1. FIND THE FILES: 
    # __file__ is a special variable that holds the path of the current file (main.py).
    # os.path.abspath(__file__) gets the full absolute path.
    # os.path.dirname(...) gets the folder containing main.py (so the project root folder).
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # We build the full paths to our excel files using os.path.join 
    # to avoid errors with slashes (like / vs \ on Windows/Mac).
    real_estate_path = os.path.join(base_dir, "Real Estate Listings.xlsx")
    marketing_path = os.path.join(base_dir, "Marketing Campaigns.xlsx")
    
    # 2. LOAD THE DATA:
    # Create an instance of DataStore (which acts like our database in memory)
    # and call initialize() to actually read the Excel files from the paths we created above.
    store = DataStore()
    store.initialize(real_estate_path, marketing_path)
    
    # 3. CREATE THE AI EXPERT:
    print("Initializing AI Agent...")
    agent = Agent() # Creates our custom Agent object.
    
    # 4. PRINT A WELCOME MESSAGE
    print("="*60)
    print("Welcome to the AI Data Assistant!")
    print("I can help you analyze and manage Real Estate Listings and Marketing Campaigns.")
    print("You can ask questions in English or Arabic.")
    print("Type 'quit' or 'exit' to leave.")
    print("="*60)
    
    # 5. START THE CHAT LOOP
    # 'while True' creates an infinite loop. It will keep running forever 
    # until we explicitly tell it to stop (using 'break' or 'sys.exit()').
    while True:
        try:
            # `input()` waits for the user to type something and press Enter.
            # `.strip()` removes any accidental extra spaces at the beginning or end of the text.
            user_input = input("\nYou: ").strip()
            
            # If the user typed 'quit' or 'exit' (in any casing, solved by .lower()), stop the loop.
            if user_input.lower() in ['quit', 'exit']:
                print("\nAssistant: Goodbye! Have a great day.")
                break # 'break' destroys the while loop and the program reaches its end.
                
            # If the user just pressed Enter without typing anything, ignore it and ask again.
            if not user_input:
                continue # 'continue' skips the rest of the code in the loop and starts from the top.
                
            # If we have real text, give it to our Agent to process. 
            # The agent will figure out the tools, get the data, and return an answer.
            response = agent.process_message(user_input)
            
            # Print the AI's final answer to the terminal.
            print(f"\nAssistant: {response}")
            
        # Exception handling: Catch specific scenarios so the program doesn't crash ugly.
        except KeyboardInterrupt:
            # This happens if the user presses Ctrl+C in the terminal to force close the app.
            print("\nAssistant: Goodbye! Have a great day.")
            sys.exit(0) # Closes the python program immediately with a success code (0).
        except Exception as e:
            # Catch ANY other random bug or error (like a network issue or missing data).
            # We print it out so it doesn't just stop the program suddenly.
            print(f"\n[System Error]: An unexpected error occurred: {str(e)}")

# This strange line tells Python: 
# "Only run the main() function if this file is run directly (python main.py)".
# If another file imports this one, it won't run main() immediately.
if __name__ == "__main__":
    main()