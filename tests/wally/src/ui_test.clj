(ns ui-test
  (:require [clojure.test :refer [deftest is]]
            [com.blockether.spel.core :as core]
            [com.blockether.spel.page :as page]
            [com.blockether.spel.locator :as loc]
            [com.blockether.spel.assertions :as a]))

(def base-url "http://localhost:18999")

(defmacro with-page [[pg] & body]
  `(core/with-testing-page {:headless true} [~pg]
     ~@body))

(defn assert! [loc & assertions]
  (let [la (a/assert-that loc)]
    (doseq [f assertions] (f la))))

;; === INDEX ===

(deftest test-index-shows-beings
  (with-page [pg]
    (page/navigate pg base-url)
    (assert! (page/locator pg ".being-link") #(a/has-count % 11))))

(deftest test-index-has-git-link
  (with-page [pg]
    (page/navigate pg base-url)
    (assert! (page/locator pg "a[href='/git']") a/is-visible)))

;; === BEING PAGE ===

(deftest test-being-page-loads
  (with-page [pg]
    (page/navigate pg (str base-url "/ember"))
    (let [text (loc/text-content (page/locator pg ".top-bar"))]
      (is (.contains text "ember"))
      (is (.contains text "events")))))

(deftest test-being-page-shows-events
  (with-page [pg]
    (page/navigate pg (str base-url "/ember"))
    (is (pos? (loc/count-elements (page/locator pg ".event"))))))

(deftest test-being-page-has-redact-button
  (with-page [pg]
    (page/navigate pg (str base-url "/ember"))
    (assert! (page/get-by-text pg "↩ redact") a/is-visible)))

(deftest test-being-page-has-push-button
  (with-page [pg]
    (page/navigate pg (str base-url "/ember"))
    (assert! (page/get-by-text pg "⬆ push git") a/is-visible)))

(deftest test-being-page-has-sse-script
  (with-page [pg]
    (page/navigate pg (str base-url "/ember"))
    (let [html (page/content pg)]
      (is (.contains html "EventSource"))
      (is (.contains html "/sse/ember")))))

;; === GIT PAGE ===

(deftest test-git-page-loads
  (with-page [pg]
    (page/navigate pg (str base-url "/git"))
    (assert! (page/locator pg ".top-bar") #(a/contains-text % "git remotes"))))

(deftest test-git-page-shows-default-remotes
  (with-page [pg]
    (page/navigate pg (str base-url "/git"))
    (let [html (page/content pg)]
      (is (.contains html "codeberg.org"))
      (is (.contains html "github.com"))
      (is (.contains html "gitlab.com")))))

(deftest test-git-page-add-and-delete-remote
  (with-page [pg]
    ;; cleanup leftovers
    (page/navigate pg (str base-url "/git"))
    (when (pos? (loc/count-elements (page/locator pg "[data-remote='wally-test']")))
      (page/evaluate pg "document.querySelector(\"[data-remote='wally-test'] form:last-of-type\").submit()")
      (Thread/sleep 1000))

    (page/navigate pg (str base-url "/git"))
    (let [add ".remote-row:not([data-remote]) "]
      (loc/fill (page/locator pg (str add "input[name='name']"))      "wally-test")
      (loc/fill (page/locator pg (str add "input[name='url']"))       "https://example.com/wally.git")
      (loc/fill (page/locator pg (str add "input[name='user']"))      "wallyuser")
      (loc/fill (page/locator pg (str add "input[name='token_var']")) "WALLY_TOKEN")
      (loc/click (page/locator pg (str add "button"))))

    (page/wait-for-url pg (str base-url "/git"))
    (assert! (page/locator pg "[data-remote='wally-test']") a/is-visible)

    ;; delete via form submit (bypasses onclick confirm)
    (page/evaluate pg "document.querySelector(\"[data-remote='wally-test'] form:last-of-type\").submit()")
    (Thread/sleep 2000)
    (page/navigate pg (str base-url "/git"))
    (assert! (page/locator pg "[data-remote='wally-test']") a/is-hidden)))
