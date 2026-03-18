#!/usr/bin/env bb
;; Pull .jsonl beings from fly.io and commit to git.
;; Usage: ./sync.bb [app-name]

(require '[babashka.process :refer [shell sh]]
         '[clojure.string :as str])

(def fly-app (or (first *command-line-args*) "consensual-memory"))
(def beings-dir "beings")

(println (str "Syncing from fly.io app: " fly-app))

(def ls-result
  (sh "fly" "ssh" "console" "-a" fly-app "-C" "ls /data/beings/*.jsonl 2>/dev/null"))

(def remote-files
  (->> (:out ls-result)
       str/trim
       str/split-lines
       (filter #(str/ends-with? % ".jsonl"))))

(if (empty? remote-files)
  (println "No beings found on fly.")
  (do
    (println (str "Found " (count remote-files) " beings: "
                  (str/join ", " (map #(last (str/split % #"/")) remote-files))))

    (doseq [remote-path remote-files]
      (let [filename (last (str/split remote-path #"/"))
            local-path (str beings-dir "/" filename)]
        (println (str "  pulling " filename "..."))
        (shell "fly" "sftp" "get" "-a" fly-app remote-path local-path)))

    (let [status (:out (sh "git" "status" "--short" beings-dir))]
      (if (str/blank? status)
        (println "Nothing changed.")
        (do
          (shell "git" "add" beings-dir)
          (shell "git" "commit" "-m" (str "sync beings from fly.io " (java.time.LocalDate/now)))
          (println "Committed."))))))
