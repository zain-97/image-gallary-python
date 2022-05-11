/**
 * Copyright 2018, Google LLC
 * Licensed under the Apache License, Version 2.0 (the `License`);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an `AS IS` BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// [START gae_python38_log]
// [START gae_python3_log]
"use strict";

window.addEventListener("load", function () {
  console.log("DOCUMENT load");
  document.getElementById("sign-out").onclick = function () {
    // ask firebase to sign out the user
    firebase.auth().signOut();
  };

  var uiConfig = {
    signInSuccessUrl: "/",
    signInOptions: [firebase.auth.EmailAuthProvider.PROVIDER_ID],
  };

  firebase.auth().onAuthStateChanged(
    function (user) {
      if (user) {
        document.getElementById("user-dropdown").hidden = false;
        document.getElementById("sign-out").hidden = false;
        document.getElementById("login-info").hidden = false;
        console.log(`Signed in as ${user.displayName} (${user.email})`);
        user.getIdToken().then(function (token) {
          document.cookie = "token=" + token;
        });
      } else {
        var ui = new firebaseui.auth.AuthUI(firebase.auth());
        ui.start("#firebase-auth-container", uiConfig);
        document.getElementById("sign-out").hidden = true;
        document.getElementById("login-info").hidden = true;
        document.getElementById("user-dropdown").hidden = true;

        document.cookie = "token=";
      }
    },
    function (error) {
      console.log(error);
      alert("Unable to log in: " + error);
    }
  );
});
// [END gae_python3_log]
// [END gae_python38_log]
