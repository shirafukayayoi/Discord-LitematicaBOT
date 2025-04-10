import csv
import os
from typing import List

import discord
from discord import app_commands


async def autocomplete_litematica_list(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    # blueprintディレクトリのパスを取得
    blueprint_dir = os.path.join(os.path.dirname(__file__), "blueprint")
    
    # ディレクトリが存在しない場合は作成
    if not os.path.exists(blueprint_dir):
        os.makedirs(blueprint_dir, exist_ok=True)
        return [app_commands.Choice(name="フォルダが空です", value="empty")]
    
    # ファイル一覧を取得
    try:
        # すべてのCSVファイル名を拡張子なしで取得
        files = [os.path.splitext(f)[0] for f in os.listdir(blueprint_dir) 
                if f.endswith('.csv')]
        
        if not files:
            return [app_commands.Choice(name="CSVファイルが見つかりません", value="no_files")]
        
        # 検索文字列でフィルタリング
        choices = []
        for file in files:
            if current.lower() in file.lower():
                choices.append(app_commands.Choice(name=file, value=file))
        
        # 最大25個まで（Discord APIの制限）
        return choices[:25]
        
    except Exception as e:
        return [app_commands.Choice(name=f"エラー: {str(e)}", value="error")]

async def autocomplete_list_check(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    options = ["finished", "unfinished", "all"]
    choices = []
    
    for option in options:
        if current.lower() in option.lower():
            choices.append(app_commands.Choice(name=option, value=option))
    
    return choices

async def autocomplete_item_name(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    """
    指定されたCSVファイル内のアイテム名を自動補完する
    """
    try:
        # オプションからlist_titleを取得
        if not interaction.namespace or not hasattr(interaction.namespace, 'list_title'):
            return [app_commands.Choice(name="まずリスト名を選択してください", value="none")]
        
        list_title = interaction.namespace.list_title
        
        # CSVファイルのパス
        blueprint_dir = os.path.join(os.path.dirname(__file__), "blueprint")
        csv_file_path = os.path.join(blueprint_dir, f"{list_title}.csv")
        
        if not os.path.exists(csv_file_path):
            return [app_commands.Choice(name=f"{list_title}.csvが見つかりません", value="not_found")]
        
        # CSVファイルからアイテム名を検索
        items = []
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # ヘッダー行をスキップ
                
                for row in reader:
                    if len(row) >= 1:
                        item_name = row[0]
                        # 検索文字列でフィルタリング
                        if current.lower() in item_name.lower():
                            items.append(app_commands.Choice(name=item_name, value=item_name))
                
            # 最大25個まで（Discord APIの制限）
            return items[:25]
        except Exception as e:
            return [app_commands.Choice(name=f"エラー: {str(e)}", value="error")]
            
    except Exception as e:
        return [app_commands.Choice(name=f"エラー: {str(e)}", value="error")]

async def autocomplete_check_status(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    """
    チェック状態の選択肢を提供する
    """
    choices = []
    options = [
        {"name": "完了", "value": "done"},
        {"name": "未完了", "value": "undone"}
    ]
    
    for option in options:
        if current.lower() in option["name"].lower() or current.lower() in option["value"].lower():
            choices.append(app_commands.Choice(name=option["name"], value=option["value"]))
    
    return choices