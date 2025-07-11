# GEMINI.md

This file provides guidance to Gemini when working with code in this repository.

## 基本方針

- **言語**: 常に日本語で応答します。
- **指示の厳守**: ユーザーの指示に正確に従います。指示されていない変更（特にUI/UX、技術スタックのバージョン）は行いません。変更が必要な場合は、必ず理由を添えて提案し、承認を得てから実行します。
- **思考プロセス**: 作業に着手する前に、思考プロセス（Plan）を簡潔に提示し、ユーザーの承認を得てから実行します。
- **既存コードの尊重**: 新しいコードを追加・変更する際は、必ず既存のファイル構成、コーディングスタイル、命名規則を踏襲します。

## 開発コマンド

- **開発サーバー起動**: `streamlit run src/app.py`

## ワークフロー

1. **分析と計画 (Analyze & Plan)**
    - ユーザーの要求を分析し、タスクを明確化します。
    - 関連ファイルを読み込み、既存の実装を調査して、重複を避けます。
    - 具体的な作業ステップを詳細にリストアップし、最適な実行順序を決定します。
    - この計画をユーザーに提示し、承認を求めます。

2. **タスクの実行 (Execute)**
    - 承認された計画に基づき、ステップを一つずつ実行します。
    - 各ステップの完了後、進捗を簡潔に報告します。

3. **品質管理 (Quality Control)**
    - コード変更後は、アプリケーションを起動し、基本的な動作確認を行います。
    - エラーが発生した場合は、原因を特定し、修正案を提示します。

4. **最終確認と報告 (Final Review & Report)**
    - すべてのタスクが完了したら、成果物が当初の要求を満たしているか最終確認します。
    - 実行した内容、変更したファイルなどをまとめて報告します。

## アーキテクチャと設計思想の理解

- このアプリケーションは、Streamlitを使用して構築されたシンプルなUIを持ち、AWS Bedrock APIと連携して動作します。
- 設定は `.streamlit/secrets.toml` で管理されます。
- プロンプトは `src/prompts` ディレクトリに分離されています。