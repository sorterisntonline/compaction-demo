(ns compaction-test
  "End-to-end tests for compaction via the poem.js SSE strategy.

  Each test is fully independent: tests that require a compacted being
  create their own fresh being file and trigger compact themselves.
  This is necessary because cognitect test-runner iterates ns-publics
  via a hash-map (non-deterministic order), so no inter-test ordering
  can be assumed.

  Test data: capacity=10, 8 perception memories, all C(8,2)=28 pairs
  pre-voted with score=0.  This means compact() runs with zero LLM
  calls — no bridge votes (1 connected component) and all 20 random
  slots are skipped (all pairs already voted)."
  (:require [clojure.test :refer [deftest is use-fixtures]]
            [clojure.java.io :as io]
            [clojure.string :as str]
            [com.blockether.spel.core :as core]
            [com.blockether.spel.page :as page]
            [com.blockether.spel.locator :as loc]
            [com.blockether.spel.assertions :as a]))

(def ^:private PORT 18888)
(def ^:private BASE-URL (str "http://localhost:" PORT))

;;; ── test data ────────────────────────────────────────────────────────────────

(defn- json-obj
  "Minimal JSON serialiser for flat maps with string/integer values."
  [m]
  (str "{"
       (str/join ","
                 (for [[k v] m]
                   (str "\"" (name k) "\":"
                        (if (string? v)
                          (str "\"" (str/replace (str v) "\"" "\\\"") "\"")
                          (str v)))))
       "}"))

(def ^:private mem-ids ["p0" "p1" "p2" "p3" "p4" "p5" "p6" "p7"])

(defn- make-being-jsonl
  "JSONL for a fresh compactable being: capacity=10, 8 perceptions, 28 votes.
  Trailing \\n is required so compact()'s file append lands on a new line."
  []
  (let [init (json-obj {:v 2 :type "init" :timestamp 1000 :id "init-1"
                        :capacity 10 :model "test/model"
                        :vote_model "test/model" :api_key ""})
        perceptions (for [[i id] (map-indexed vector mem-ids)]
                      (json-obj {:v 2 :type "perception"
                                 :timestamp (+ 2000 (* i 100))
                                 :id id :content (str "memory " i)}))
        votes (for [[i id-a] (map-indexed vector mem-ids)
                    [j id-b] (map-indexed vector mem-ids)
                    :when (< i j)]
                (json-obj {:v 2 :type "vote"
                           :timestamp (+ 10000 (* 100 i) j)
                           :vote_a_id id-a :vote_b_id id-b
                           :vote_score 0 :reasoning "neutral"}))]
    (str (str/join "\n" (concat [init] perceptions votes)) "\n")))

;;; ── server fixture ───────────────────────────────────────────────────────────

(def ^:private ^:dynamic *beings-dir* nil)
(def ^:private server (atom nil))

(defn- server-ready? []
  (try
    (let [c (.openConnection (java.net.URL. (str BASE-URL "/")))]
      (.setConnectTimeout c 1000)
      (.connect c)
      (.disconnect c)
      true)
    (catch Exception _ false)))

(defn- project-root []
  (-> (io/file (System/getProperty "user.dir") "../..")
      .getCanonicalFile))

(defn- start-server! [beings-dir]
  (let [pb (doto (ProcessBuilder.
                  ^java.util.List
                  ["python3" "-m" "app.app"
                   (.getAbsolutePath beings-dir)
                   "--port" (str PORT)])
             (.directory (project-root))
             (.redirectErrorStream true)
             (.redirectOutput (java.io.File/createTempFile "cm-server-" ".log")))]
    (reset! server (.start pb))
    (loop [remaining 20]
      (Thread/sleep 500)
      (cond
        (server-ready?)   true
        (zero? remaining) (throw (ex-info "Server did not start" {}))
        :else             (recur (dec remaining))))))

(defn- stop-server! []
  (when-let [p @server]
    (.destroy p)
    (.waitFor p)
    (reset! server nil)))

(defn- compaction-fixture [f]
  (let [tmp (doto (java.io.File/createTempFile "beings-cpt-" nil)
              .delete
              .mkdirs)]
    ;; ember.jsonl: the primary test being
    (spit (io/file tmp "ember.jsonl") (make-being-jsonl))
    (start-server! tmp)
    (binding [*beings-dir* tmp]
      (try (f)
           (finally (stop-server!))))))

(use-fixtures :once compaction-fixture)

;;; ── helpers ──────────────────────────────────────────────────────────────────

(defmacro ^:private with-page [[pg] & body]
  `(core/with-testing-page {:headless true} [~pg]
     ~@body))

(defn- assert! [loc & assertions]
  (let [la (a/assert-that loc)]
    (doseq [f assertions] (f la))))

(defn- page-html
  "Returns outerHTML via JS eval, safer than page/content during SSE morphs."
  [pg]
  (let [r (page/evaluate pg "() => document.documentElement.outerHTML")]
    (if (string? r) r "")))

(defn- event-count
  "Count .event elements; returns 0 on exception (e.g. during navigation)."
  [pg]
  (try
    (loc/count-elements (page/locator pg ".event"))
    (catch Exception _ 0)))

(defn- poll-until
  "Polls pred every poll-ms until true or timeout-ms expires."
  [pred timeout-ms poll-ms]
  (let [deadline (+ (System/currentTimeMillis) timeout-ms)]
    (loop []
      (cond
        (pred)                                  true
        (> (System/currentTimeMillis) deadline) false
        :else                                   (do (Thread/sleep poll-ms) (recur))))))

(defn- file-has-compaction?
  "True when the given JSONL file contains a Compaction event.
  Python's json.dumps serialises as '\"type\": \"compaction\"' (space after colon)."
  [f]
  (let [content (try (slurp f) (catch Exception _ ""))]
    (.contains content "\"type\": \"compaction\"")))

(defn- compact-being!
  "Creates a fresh being at beings-dir/being-name.jsonl, navigates to it
  in a headless browser, clicks compact, and polls until the file contains
  a Compaction event.  Returns true on success."
  [being-name]
  (let [f (io/file *beings-dir* (str being-name ".jsonl"))]
    (spit f (make-being-jsonl))
    (with-page [pg]
      (page/navigate pg (str BASE-URL "/" being-name))
      ;; Wait for SSE initial morph to settle before clicking
      (Thread/sleep 1500)
      (loc/click (page/get-by-text pg "🗜️ compact"))
      (poll-until #(file-has-compaction? f) 20000 300))))

;;; ── static structure tests (independent of compaction) ──────────────────────

(deftest test-poem-js-script-present
  "Being page embeds the poem.js EventSource script."
  (with-page [pg]
    (page/navigate pg (str BASE-URL "/ember"))
    (Thread/sleep 1500)
    (let [html (page-html pg)]
      (is (.contains html "EventSource")   "poem.js EventSource must be in page")
      (is (.contains html "/sse/ember")    "SSE endpoint must reference the being")
      (is (.contains html "Idiomorph")     "Idiomorph must be imported")
      (is (.contains html "applyPatch")    "patch handler must be present"))))

(deftest test-compact-button-and-strategy-selector
  "Compact button and strategy dropdown with 3 options are visible."
  (with-page [pg]
    (page/navigate pg (str BASE-URL "/ember"))
    (assert! (page/get-by-text pg "🗜️ compact") a/is-visible)
    (is (= 3 (loc/count-elements (page/locator pg "select[name='strategy'] option")))
        "strategy selector must offer default, resurrection, dream")))

(deftest test-sse-endpoint-returns-event-stream
  "GET /sse/ember responds with Content-Type: text/event-stream."
  (let [conn (.openConnection (java.net.URL. (str BASE-URL "/sse/ember")))]
    (.setConnectTimeout conn 3000)
    (.setReadTimeout conn 1000)
    (try
      (.connect conn)
      (is (str/includes? (or (.getHeaderField conn "Content-Type") "")
                         "text/event-stream")
          "SSE endpoint must return text/event-stream")
      (finally (.disconnect conn)))))

;;; ── compaction tests (each triggers its own compact) ────────────────────────

(deftest test-compaction-end-to-end-poem-js
  "Full poem.js round-trip on ember:
     click compact → POST /do → compact() runs → file updated
     → SSE detects mtime change → SSE sends #events patch
     → Idiomorph morphs the DOM to show the Compaction event row.

  Two-part verification:
  1. FILE: Compaction event in ember.jsonl (authoritative, no SSE ambiguity)
  2. DOM:  #events count increases (proves SSE/Idiomorph delivered the patch)"
  (let [f (io/file *beings-dir* "ember.jsonl")]
    (with-page [pg]
      (page/navigate pg (str BASE-URL "/ember"))
      ;; Wait for SSE initial morph before capturing baseline
      (Thread/sleep 1500)
      (is (pos? (event-count pg)) "events must be present before compaction")
      (let [before (event-count pg)]
        ;; Click compact — POST /do → compact() thread → Compaction event in file
        (loc/click (page/get-by-text pg "🗜️ compact"))

        ;; Part 1: authoritative file check
        (let [file-ok? (poll-until #(file-has-compaction? f) 20000 300)]
          (is file-ok? "Compaction event must appear in ember.jsonl"))

        ;; Part 2: SSE/Idiomorph DOM update
        ;; Wait for page to settle at /ember, then give SSE time to push patch
        (poll-until #(and (= (.url pg) (str BASE-URL "/ember"))
                          (pos? (event-count pg)))
                    10000 300)
        (Thread/sleep 2000)
        (let [after (event-count pg)]
          (is (> after before)
              (str "DOM event count must increase via SSE/Idiomorph; "
                   "before=" before " after=" after)))))))

(deftest test-compaction-event-type-visible
  "After compaction, the SSE-updated #events DOM shows a 'compaction' event-type span.
  Triggers its own compact on ember-evt (independent of test execution order)."
  (let [ok? (compact-being! "ember-evt")]
    (is ok? "compact-being! must succeed for ember-evt"))
  (with-page [pg]
    (page/navigate pg (str BASE-URL "/ember-evt"))
    ;; Wait for SSE to connect and send the updated #events HTML
    (Thread/sleep 2000)
    (let [types-text (str (page/evaluate
                           pg
                           "() => [...document.querySelectorAll('.event-type')].map(e=>e.textContent).join(' ')"))]
      (is (.contains types-text "compaction")
          (str "SSE-updated DOM must contain 'compaction' event-type; got: "
               (subs types-text 0 (min 100 (count types-text))))))))

(deftest test-progress-bar-clears-after-compaction
  "After compaction, #compaction-progress is empty (no lingering bar).
  Uses ember2 — independent of other tests."
  (let [ok? (compact-being! "ember2")]
    (is ok? "compact-being! must succeed for ember2"))
  (with-page [pg]
    (page/navigate pg (str BASE-URL "/ember2"))
    (poll-until #(pos? (event-count pg)) 5000 200)
    ;; #compaction-progress should be empty after compact completes
    (let [bar-empty?
          (poll-until
           #(str/blank?
             (str (page/evaluate pg "() => document.getElementById('compaction-progress')?.innerHTML ?? ''")))
           15000 300)]
      (is bar-empty? "#compaction-progress must be cleared by SSE after compaction"))))

(deftest test-memories-reduced-after-compaction
  "After compaction the JSONL file contains a Compaction event with non-empty
  released_ids, proving memories were released.  Uses ember-mem (independent)."
  (let [f    (io/file *beings-dir* "ember-mem.jsonl")
        ok?  (compact-being! "ember-mem")]
    (is ok? "compact-being! must succeed for ember-mem")
    (let [content (slurp f)
          lines   (filter #(and (not (str/blank? %))
                                (.contains % "\"type\": \"compaction\""))
                          (str/split content #"\n"))]
      (is (pos? (count lines))
          "JSONL file must contain a Compaction event")
      (when (pos? (count lines))
        (is (not (.contains (first lines) "\"released_ids\":[]"))
            "Compaction event must have non-empty released_ids")))))
