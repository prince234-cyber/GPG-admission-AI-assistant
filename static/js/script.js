// ============================================================
// GPG AI ADMISSION ASSISTANT
// CHAT + VOICE INPUT
// English + Hindi + Gujarati
// ============================================================


// ============================================================
// DOM ELEMENTS
// ============================================================

const sendButton =
    document.getElementById("send-btn");

const userInput =
    document.getElementById("user-input");

const chatBox =
    document.getElementById("chat-box");

const voiceBtn =
    document.getElementById("voice-btn");

const voiceAnimation =
    document.getElementById("voice-animation");

const voiceStatus =
    document.getElementById("voice-status");

const languageSelect =
    document.getElementById("language-select");


// ============================================================
// APPLICATION STATE
// ============================================================

let isSending = false;

let typingMessage = null;


// ============================================================
// QUICK QUESTIONS
// ============================================================

const quickQuestionButtons =
    document.querySelectorAll(
        ".quick-questions button"
    );


quickQuestionButtons.forEach(
    function (button) {

        button.addEventListener(
            "click",
            function () {

                const question =
                    button.dataset.question;

                if (!question) {

                    return;

                }

                userInput.value =
                    question;

                userInput.focus();

                sendMessage();

            }
        );

    }
);


// ============================================================
// SEND BUTTON
// ============================================================

sendButton.addEventListener(
    "click",
    sendMessage
);


// ============================================================
// ENTER KEY
// ============================================================

userInput.addEventListener(
    "keydown",
    function (event) {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            sendMessage();

        }

    }
);


// ============================================================
// SEND MESSAGE
// ============================================================

async function sendMessage() {

    const message =
        userInput.value.trim();


    // Do not send empty message

    if (message === "") {

        return;

    }


    // Prevent multiple requests

    if (isSending) {

        return;

    }


    // --------------------------------------------------------
    // Stop voice recognition if active
    // --------------------------------------------------------

    if (
        typeof isRecording !== "undefined" &&
        isRecording
    ) {

        try {

            recognition.stop();

        } catch (error) {

            console.log(
                "Voice stop error:",
                error
            );

        }

    }


    // --------------------------------------------------------
    // Set sending state
    // --------------------------------------------------------

    isSending = true;

    sendButton.disabled = true;


    // --------------------------------------------------------
    // Show user message
    // --------------------------------------------------------

    addUserMessage(message);


    // Clear input

    userInput.value = "";


    // --------------------------------------------------------
    // Show typing
    // --------------------------------------------------------

    showTyping();


    console.log(
        "Sending question to Flask:",
        message
    );


    try {


        // ====================================================
        // SEND REQUEST
        // ====================================================

        const response =
            await fetch(
                "/chat",
                {

                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body: JSON.stringify({

                        message: message

                    })

                }
            );


        // ====================================================
        // READ RESPONSE
        // ====================================================

        let data;

        try {

            data =
                await response.json();

        } catch (jsonError) {

            throw new Error(
                "The server returned an invalid response."
            );

        }


        // ====================================================
        // SERVER ERROR
        // ====================================================

        if (!response.ok) {

            throw new Error(
                data.reply ||
                data.error ||
                "Server error. Please try again."
            );

        }


        // ====================================================
        // REMOVE TYPING
        // ====================================================

        removeTyping();


        // ====================================================
        // DISPLAY BOT RESPONSE
        // ====================================================

        addBotMessage(
            data.reply ||
            "I couldn't find an answer to that question."
        );


    } catch (error) {


        console.error(
            "Chat error:",
            error
        );


        removeTyping();


        addBotMessage(

            "Sorry, I couldn't process your question right now. " +
            "Please try again."

        );

    } finally {


        // ----------------------------------------------------
        // Reset sending state
        // ----------------------------------------------------

        isSending = false;

        sendButton.disabled = false;

        userInput.focus();

    }

}


// ============================================================
// ADD USER MESSAGE
// ============================================================

function addUserMessage(message) {


    const html =
        '<div class="message user-message">' +
            '<div class="message-content">' +
                '<h4>Student</h4>' +
                '<p>' + escapeHtml(message) + '</p>' +
            '</div>' +
            '<img src="/static/images/user.png" ' +
                'class="avatar" alt="Student">' +
        '</div>';


    chatBox.insertAdjacentHTML(
        "beforeend",
        html
    );


    scrollChat();

}


// ============================================================
// ADD BOT MESSAGE
// ============================================================

function addBotMessage(message) {


    let formattedMessage;


    // --------------------------------------------------------
    // Markdown
    // --------------------------------------------------------

    if (
        typeof marked !== "undefined"
    ) {

        try {

            formattedMessage =
                marked.parse(
                    String(message)
                );

        } catch (error) {

            console.error(
                "Markdown parsing error:",
                error
            );

            formattedMessage =
                escapeHtml(
                    String(message)
                ).replace(
                    /\n/g,
                    "<br>"
                );

        }

    } else {

        formattedMessage =
            escapeHtml(
                String(message)
            ).replace(
                /\n/g,
                "<br>"
            );

    }


    // --------------------------------------------------------
    // Bot message HTML
    // --------------------------------------------------------

    const html =
        '<div class="message bot-message">' +
            '<img src="/static/images/bot.png" ' +
                'class="avatar" alt="GPG AI Assistant">' +
            '<div class="message-content">' +
                '<div class="message-title">' +
                    '<h2>GPG Admission Assistant</h2>' +
                    '<span class="verified-badge" ' +
                        'title="Official Assistant">✓</span>' +
                '</div>' +
                '<div class="ai-text">' + formattedMessage + '</div>' +
            '</div>' +
        '</div>';


    chatBox.insertAdjacentHTML(
        "beforeend",
        html
    );


    scrollChat();

}


// ============================================================
// ESCAPE HTML
// ============================================================

function escapeHtml(text) {


    const div =
        document.createElement(
            "div"
        );


    div.textContent =
        text;


    return div.innerHTML;

}


// ============================================================
// AUTO SCROLL
// ============================================================

function scrollChat() {


    requestAnimationFrame(
        function () {

            chatBox.scrollTop =
                chatBox.scrollHeight;

        }
    );

}


// ============================================================
// TYPING INDICATOR
// ============================================================

function showTyping() {


    removeTyping();


    typingMessage =
        document.createElement(
            "div"
        );


    typingMessage.className =
        "message bot-message";


    typingMessage.id =
        "typing-message";


    typingMessage.innerHTML =
        '<img src="/static/images/bot.png" ' +
            'class="avatar" alt="GPG AI Assistant">' +
        '<div class="message-content">' +
            '<div class="message-title">' +
                '<h2>GPG Admission Assistant</h2>' +
                '<span class="verified-badge" ' +
                    'title="Official Assistant">✓</span>' +
            '</div>' +
            '<div class="typing" ' +
                'aria-label="Assistant is typing">' +
                '<span></span><span></span><span></span>' +
            '</div>' +
        '</div>';


    chatBox.appendChild(
        typingMessage
    );


    scrollChat();

}


// ============================================================
// REMOVE TYPING
// ============================================================

function removeTyping() {


    const typing =
        document.getElementById(
            "typing-message"
        );


    if (typing) {

        typing.remove();

    }


    typingMessage = null;

}


// ============================================================
// VOICE RECOGNITION
// ============================================================

const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;


// ============================================================
// CHECK BROWSER SUPPORT
// ============================================================

if (!SpeechRecognition) {


    voiceBtn.disabled = true;


    voiceBtn.title =
        "Voice input is not supported in this browser";


    voiceBtn.setAttribute(
        "aria-label",
        "Voice input is not supported"
    );


    console.warn(
        "Speech Recognition is not supported."
    );


} else {


    // ========================================================
    // CREATE RECOGNITION
    // ========================================================

    const recognition =
        new SpeechRecognition();


    // ========================================================
    // RECOGNITION SETTINGS
    // ========================================================

    recognition.continuous =
        true;

    recognition.interimResults =
        true;

    recognition.maxAlternatives =
        1;


    // ========================================================
    // VOICE STATE
    // ========================================================

    let isRecording =
        false;

    let userStopped =
        false;


    // ========================================================
    // GET LANGUAGE
    // ========================================================

    function getSelectedLanguage() {


        if (!languageSelect) {

            return "en-IN";

        }


        return languageSelect.value ||
            "en-IN";

    }


    // ========================================================
    // START RECORDING
    // ========================================================

    function startRecording() {


        if (isRecording) {

            return;

        }


        userStopped =
            false;


        recognition.lang =
            getSelectedLanguage();


        console.log(
            "Starting voice recognition:",
            recognition.lang
        );


        try {

            recognition.start();

        } catch (error) {

            console.log(
                "Recognition start:",
                error
            );

        }

    }


    // ========================================================
    // STOP RECORDING
    // ========================================================

    function stopRecording() {


        userStopped =
            true;


        if (!isRecording) {

            resetVoiceUI();

            return;

        }


        console.log(
            "Stopping voice recognition..."
        );


        try {

            recognition.stop();

        } catch (error) {

            console.log(
                "Recognition stop error:",
                error
            );

            resetVoiceUI();

        }

    }


    // ========================================================
    // MICROPHONE BUTTON
    // ========================================================

    voiceBtn.addEventListener(
        "click",
        function () {


            if (isRecording) {

                stopRecording();

            } else {

                startRecording();

            }

        }
    );


    // ========================================================
    // LANGUAGE CHANGE
    // ========================================================

    languageSelect.addEventListener(
        "change",
        function () {


            const selectedLanguage =
                getSelectedLanguage();


            console.log(
                "Language changed:",
                selectedLanguage
            );


            if (isRecording) {


                stopRecording();


                setTimeout(
                    function () {

                        startRecording();

                    },
                    300
                );

            }

        }
    );


    // ========================================================
    // RECOGNITION START
    // ========================================================

    recognition.onstart =
        function () {


            console.log(
                "Microphone is listening..."
            );


            isRecording =
                true;


            // Change microphone to stop icon

            voiceBtn.innerHTML =
                "⏹️";


            voiceBtn.classList.add(
                "recording"
            );


            voiceBtn.title =
                "Stop voice input";


            voiceBtn.setAttribute(
                "aria-label",
                "Stop voice input"
            );


            // Voice animation

            voiceAnimation.classList.add(
                "active"
            );


            // Voice status

            if (voiceStatus) {

                voiceStatus.classList.add(
                    "active"
                );

            }

        };


    // ========================================================
    // RECOGNITION RESULT
    // ========================================================

    recognition.onresult =
        function (event) {


            let finalTranscript =
                "";

            let interimTranscript =
                "";


            for (
                let i = event.resultIndex;
                i < event.results.length;
                i++
            ) {


                const transcript =
                    event.results[i][0]
                        .transcript;


                if (
                    event.results[i]
                        .isFinal
                ) {


                    finalTranscript +=
                        transcript + " ";


                } else {


                    interimTranscript +=
                        transcript;

                }

            }


            // ------------------------------------------------
            // FINAL SPEECH
            // ------------------------------------------------

            if (
                finalTranscript.trim() !== ""
            ) {


                const existingText =
                    userInput.value.trim();


                if (
                    existingText === ""
                ) {


                    userInput.value =
                        finalTranscript.trim();


                } else {


                    userInput.value =
                        existingText +
                        " " +
                        finalTranscript.trim();

                }


                console.log(
                    "Final speech:",
                    finalTranscript
                );


                // Put cursor at end

                userInput.focus();

                userInput.setSelectionRange(
                    userInput.value.length,
                    userInput.value.length
                );

            }


            // ------------------------------------------------
            // INTERIM SPEECH
            // ------------------------------------------------

            if (
                interimTranscript.trim() !== ""
            ) {


                console.log(
                    "Listening:",
                    interimTranscript
                );

            }

        };


    // ========================================================
    // SPEECH END
    // ========================================================

    recognition.onspeechend =
        function () {


            console.log(
                "Speech ended."
            );


            /*
             * Do not stop recognition here.
             *
             * Chrome may stop after silence.
             * onend handles restarting.
             */

        };


    // ========================================================
    // RECOGNITION END
    // ========================================================

    recognition.onend =
        function () {


            console.log(
                "Recognition ended."
            );


            // ------------------------------------------------
            // User intentionally stopped
            // ------------------------------------------------

            if (userStopped) {


                resetVoiceUI();

                return;

            }


            // ------------------------------------------------
            // Browser automatically stopped
            // ------------------------------------------------

            if (isRecording) {


                try {


                    setTimeout(
                        function () {


                            if (
                                isRecording &&
                                !userStopped
                            ) {


                                try {

                                    recognition.start();

                                } catch (error) {

                                    console.log(
                                        "Recognition restart:",
                                        error
                                    );

                                }

                            }

                        },
                        200
                    );


                } catch (error) {

                    console.log(
                        "Recognition restart error:",
                        error
                    );

                }


            } else {


                resetVoiceUI();

            }

        };


    // ========================================================
    // RECOGNITION ERROR
    // ========================================================

    recognition.onerror =
        function (event) {


            console.log(
                "Speech recognition error:",
                event.error
            );


            // ------------------------------------------------
            // Permission denied
            // ------------------------------------------------

            if (
                event.error ===
                "not-allowed"
            ) {


                alert(
                    "Microphone permission was denied. " +
                    "Please allow microphone access in your browser."
                );


                userStopped =
                    true;


                resetVoiceUI();


                return;

            }


            // ------------------------------------------------
            // Microphone unavailable
            // ------------------------------------------------

            if (
                event.error ===
                "audio-capture"
            ) {


                alert(
                    "Microphone could not be accessed. " +
                    "Please check your microphone."
                );


                userStopped =
                    true;


                resetVoiceUI();


                return;

            }


            // ------------------------------------------------
            // No speech
            // ------------------------------------------------

            if (
                event.error ===
                "no-speech"
            ) {


                /*
                 * No alert here.
                 *
                 * onend will restart recognition.
                 */

                return;

            }


            // ------------------------------------------------
            // Aborted
            // ------------------------------------------------

            if (
                event.error ===
                "aborted"
            ) {


                return;

            }


            // ------------------------------------------------
            // Network error
            // ------------------------------------------------

            if (
                event.error ===
                "network"
            ) {


                console.warn(
                    "Speech recognition network error."
                );


                return;

            }


            // ------------------------------------------------
            // Other errors
            // ------------------------------------------------

            console.warn(
                "Voice recognition problem:",
                event.error
            );

        };


    // ========================================================
    // RESET VOICE UI
    // ========================================================

    function resetVoiceUI() {


        isRecording =
            false;


        voiceBtn.innerHTML =
            "🎙️";


        voiceBtn.classList.remove(
            "recording"
        );


        voiceBtn.title =
            "Start voice input";


        voiceBtn.setAttribute(
            "aria-label",
            "Start voice input"
        );


        voiceAnimation.classList.remove(
            "active"
        );


        if (voiceStatus) {

            voiceStatus.classList.remove(
                "active"
            );

        }

    }

}


// ============================================================
// INITIAL FOCUS
// ============================================================

window.addEventListener(
    "load",
    function () {

        if (userInput) {

            userInput.focus();

        }

    }
);
