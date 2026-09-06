import os
import json
import websocket
from dotenv import load_dotenv

load_dotenv()


INWORLD_KEY = os.getenv("INWORLD_API_KEY")


INWORLD_URL = (
    "wss://api.inworld.ai/api/v1/realtime/session"
    "?key=voice-123456"
    "&protocol=realtime"
)



def connect_inworld():

    ws = websocket.create_connection(
        INWORLD_URL,
        header=[
            f"Authorization: Basic {INWORLD_KEY}"
        ]
    )


    # receive session.created
    event = ws.recv()

    print("Connected:", event)



    session_config = {

        "type": "session.update",

        "session": {

            "type": "realtime",

            "model":
            "inworld/models/gemma-4-26b-a4b-it",


            "instructions":
            """
            You are GPG Admission Assistant.

            Answer only Government Polytechnic
            Gandhinagar admission questions.

            Reply in Gujarati, Hindi or English
            based on student language.

            Do not answer unrelated questions.
            """,


            "output_modalities":[
                "audio"
            ],


            "audio": {

                "input": {

                    "transcription": {
                        "model":
                        "assemblyai/u3-rt-pro"
                    },

                    "turn_detection":{
                        "type":"semantic_vad",
                        "eagerness":"medium",
                        "create_response":True,
                        "interrupt_response":True
                    }
                },


                "output":{

                    "model":
                    "inworld-tts-2",

                    "voice":
                    "Aarav"
                }
            }
        }
    }



    ws.send(
        json.dumps(session_config)
    )


    return ws