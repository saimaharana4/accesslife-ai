/** UI-only invented contracts. These are not the future API or Qloo schemas. */
export type FixtureStory =
  | "normal"
  | "empty"
  | "partial"
  | "retry"
  | "expired"
  | "interrupted"
  | "long-title"
  | "missing-image"
  | "preparing"
  | "submitting"
  | "selected"
  | "disabled"
  | "pending";
export type FixtureSeed = {
  id: string;
  name: string;
  type: string;
  detail: string;
};
export type FixtureChoice = {
  id: string;
  title: string;
  kind: "Fictional film";
  art: string;
};
export type FixtureRound = {
  id: string;
  ordinal: number;
  choices: [FixtureChoice, FixtureChoice];
};
export type FixtureGameInfo = {
  id: string;
  seed: FixtureSeed;
  total: 5;
  story: FixtureStory;
};
export type FixtureAnswer = {
  roundId: string;
  ordinal: number;
  choiceId: string;
  winnerId: string;
  correct: boolean;
  winnerTitle: string;
  selectedTitle: string;
};
export type Progress = {
  game: FixtureGameInfo;
  round: FixtureRound;
  answers: FixtureAnswer[];
  discoveries: FixtureChoice[];
};
export type FixtureIssue =
  | "empty"
  | "partial"
  | "expired"
  | "interrupted"
  | "retry";
export type Recovery =
  | { kind: "start"; seed: FixtureSeed; story: FixtureStory; key: string }
  | { kind: "answer"; progress: Progress; choiceId: string; key: string }
  | { kind: "advance"; progress: Progress; answer: FixtureAnswer; key: string };
export type FixtureState =
  | { kind: "idle" }
  | {
      kind: "preparing";
      operation: number;
      seed: FixtureSeed;
      story: FixtureStory;
      key: string;
    }
  | ({ kind: "unanswered" } & Progress)
  | ({
      kind: "submitting";
      operation: number;
      choiceId: string;
      key: string;
    } & Progress)
  | ({ kind: "revealed"; answer: FixtureAnswer } & Progress)
  | ({
      kind: "advancing";
      operation: number;
      answer: FixtureAnswer;
      key: string;
    } & Progress)
  | {
      kind: "complete";
      game: FixtureGameInfo;
      answers: FixtureAnswer[];
      discoveries: FixtureChoice[];
    }
  | {
      kind: "issue";
      issue: FixtureIssue;
      message: string;
      recovery?: Recovery;
    };

export type StartResult =
  | { kind: "ready"; game: FixtureGameInfo; round: FixtureRound }
  | { kind: "empty" | "partial"; available: number };
export type AdvanceResult =
  | { kind: "round"; round: FixtureRound }
  | { kind: "complete" };
export interface FixtureTransport {
  start(
    seed: FixtureSeed,
    story: FixtureStory,
    key: string,
    signal?: AbortSignal,
  ): Promise<StartResult>;
  answer(
    gameId: string,
    roundId: string,
    choiceId: string,
    key: string,
    signal?: AbortSignal,
  ): Promise<FixtureAnswer>;
  advance(
    gameId: string,
    roundId: string,
    key: string,
    signal?: AbortSignal,
  ): Promise<AdvanceResult>;
}
