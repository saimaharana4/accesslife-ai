import type {
  AdvanceResult,
  FixtureAnswer,
  FixtureChoice,
  FixtureIssue,
  FixtureSeed,
  FixtureState,
  FixtureStory,
  Progress,
  Recovery,
  StartResult,
} from "./types.ts";

export type FixtureEvent =
  | {
      type: "START";
      operation: number;
      seed: FixtureSeed;
      story: FixtureStory;
      key: string;
    }
  | { type: "STARTED"; operation: number; result: StartResult }
  | { type: "ANSWER"; operation: number; choiceId: string; key: string }
  | { type: "ANSWERED"; operation: number; answer: FixtureAnswer }
  | { type: "ADVANCE"; operation: number; key: string }
  | { type: "ADVANCED"; operation: number; result: AdvanceResult }
  | { type: "ISSUE"; operation: number; issue: FixtureIssue; message: string }
  | { type: "INTERRUPT" }
  | { type: "STORY"; issue: FixtureIssue; message: string }
  | { type: "RETRY"; operation: number }
  | { type: "SAVE"; choice: FixtureChoice }
  | { type: "RESET" };

export function fixtureScore(answers: readonly FixtureAnswer[]) {
  return answers.filter((answer) => answer.correct).length;
}
export function isBusy(state: FixtureState) {
  return (
    state.kind === "preparing" ||
    state.kind === "submitting" ||
    state.kind === "advancing"
  );
}
export function progressOf(state: Progress): Progress {
  return {
    game: state.game,
    round: state.round,
    answers: state.answers,
    discoveries: state.discoveries,
  };
}
function recoveryOf(state: FixtureState): Recovery | undefined {
  if (state.kind === "preparing")
    return {
      kind: "start",
      seed: state.seed,
      story: state.story,
      key: state.key,
    };
  if (state.kind === "submitting")
    return {
      kind: "answer",
      progress: progressOf(state),
      choiceId: state.choiceId,
      key: state.key,
    };
  if (state.kind === "advancing")
    return {
      kind: "advance",
      progress: progressOf(state),
      answer: state.answer,
      key: state.key,
    };
  return undefined;
}

export function fixtureReducer(
  state: FixtureState,
  event: FixtureEvent,
): FixtureState {
  switch (event.type) {
    case "RESET":
      return { kind: "idle" };
    case "STORY":
      return { kind: "issue", issue: event.issue, message: event.message };
    case "START":
      if (isBusy(state)) return state;
      return {
        kind: "preparing",
        operation: event.operation,
        seed: event.seed,
        story: event.story,
        key: event.key,
      };
    case "STARTED":
      if (state.kind !== "preparing" || state.operation !== event.operation)
        return state;
      if (event.result.kind !== "ready")
        return {
          kind: "issue",
          issue: event.result.kind,
          message:
            event.result.kind === "empty"
              ? "This fixture contains no eligible rounds. Choose the full fixture to continue."
              : `Only ${event.result.available} fixture rounds are available. A five-round game cannot start.`,
          recovery: recoveryOf(state),
        };
      return {
        kind: "unanswered",
        game: event.result.game,
        round: event.result.round,
        answers: [],
        discoveries: [],
      };
    case "ANSWER":
      if (
        state.kind !== "unanswered" ||
        !state.round.choices.some((choice) => choice.id === event.choiceId)
      )
        return state;
      return {
        ...progressOf(state),
        kind: "submitting",
        operation: event.operation,
        choiceId: event.choiceId,
        key: event.key,
      };
    case "ANSWERED": {
      if (
        state.kind !== "submitting" ||
        state.operation !== event.operation ||
        state.round.id !== event.answer.roundId ||
        state.choiceId !== event.answer.choiceId
      )
        return state;
      if (
        state.answers.some((answer) => answer.roundId === event.answer.roundId)
      )
        return state;
      return {
        ...progressOf(state),
        kind: "revealed",
        answer: event.answer,
        answers: [...state.answers, event.answer],
      };
    }
    case "ADVANCE":
      if (state.kind !== "revealed") return state;
      return {
        ...progressOf(state),
        kind: "advancing",
        answer: state.answer,
        operation: event.operation,
        key: event.key,
      };
    case "ADVANCED":
      if (state.kind !== "advancing" || state.operation !== event.operation)
        return state;
      if (event.result.kind === "complete") {
        if (state.answers.length !== state.game.total) return state;
        return {
          kind: "complete",
          game: state.game,
          answers: state.answers,
          discoveries: state.discoveries,
        };
      }
      if (event.result.round.ordinal !== state.round.ordinal + 1) return state;
      return {
        ...progressOf(state),
        kind: "unanswered",
        round: event.result.round,
      };
    case "ISSUE":
      if (!("operation" in state) || state.operation !== event.operation)
        return state;
      return {
        kind: "issue",
        issue: event.issue,
        message: event.message,
        recovery: recoveryOf(state),
      };
    case "INTERRUPT":
      if (!isBusy(state)) return state;
      return {
        kind: "issue",
        issue: "interrupted",
        message:
          "The fixture action was interrupted. Resume it using the same local request; a refresh resets all fixture memory.",
        recovery: recoveryOf(state),
      };
    case "RETRY": {
      if (state.kind !== "issue" || !state.recovery) return state;
      const recovery = state.recovery;
      if (recovery.kind === "start")
        return {
          kind: "preparing",
          operation: event.operation,
          seed: recovery.seed,
          story: recovery.story,
          key: recovery.key,
        };
      if (recovery.kind === "answer")
        return {
          ...recovery.progress,
          kind: "submitting",
          operation: event.operation,
          choiceId: recovery.choiceId,
          key: recovery.key,
        };
      return {
        ...recovery.progress,
        kind: "advancing",
        operation: event.operation,
        answer: recovery.answer,
        key: recovery.key,
      };
    }
    case "SAVE": {
      if (
        !("discoveries" in state) ||
        !(state.kind === "revealed" || state.kind === "complete")
      )
        return state;
      const found = state.discoveries.some(
        (choice) => choice.id === event.choice.id,
      );
      return {
        ...state,
        discoveries: found
          ? state.discoveries.filter((choice) => choice.id !== event.choice.id)
          : [...state.discoveries, event.choice],
      };
    }
  }
}
