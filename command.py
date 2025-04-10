import csv
import datetime
import os
import re
import shutil

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View  # ボタン機能のインポート

from autocomplete import (autocomplete_check_status, autocomplete_item_name,
                          autocomplete_list_check,
                          autocomplete_litematica_list)


# ページネーション用のViewクラス
class ItemPaginationView(discord.ui.View):
    def __init__(self, items, check_status, list_title, interaction_user):
        super().__init__(timeout=180)  # 3分間のタイムアウト
        self.items = items
        self.current_page = 0
        self.items_per_page = 20
        self.check_status = check_status
        self.list_title = list_title
        self.user = interaction_user
        self.total_pages = (len(items) - 1) // self.items_per_page + 1
        
        # 最初のページでは前へボタンを無効化
        self.update_button_states()
    
    def update_button_states(self):
        # 前へボタン（最初のページでは無効）
        self.children[0].disabled = (self.current_page == 0)
        # 次へボタン（最後のページでは無効）
        self.children[1].disabled = (self.current_page >= self.total_pages - 1)
    
    @discord.ui.button(label="前へ", style=discord.ButtonStyle.primary, emoji="⬅️")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 権限チェック
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("このボタンは使用できません。", ephemeral=True)
            return
        
        self.current_page -= 1
        self.update_button_states()
        
        # 新しいページのEmbedを作成
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="次へ", style=discord.ButtonStyle.primary, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 権限チェック
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("このボタンは使用できません。", ephemeral=True)
            return
        
        self.current_page += 1
        self.update_button_states()
        
        # 新しいページのEmbedを作成
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    def create_embed(self):
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.items))
        
        # "all"の場合は適切なステータステキストを設定
        if self.check_status == "all":
            status_text = "全て"
        else:
            status_text = "完了済み" if self.check_status == "finished" else "未完了"
        
        embed = discord.Embed(
            title=f"{self.list_title} - {status_text}アイテム一覧",
            description=f"**{len(self.items)}個**のアイテムが表示されています。(ページ {self.current_page + 1}/{self.total_pages})",
            color=0x00FF00 if self.check_status == "finished" else (0x0000FF if self.check_status == "unfinished" else 0x9932CC)  # allは紫色
        )
        
        counter = start_idx
        page_total = 0
        
        for name, count, checked in self.items[start_idx:end_idx]:
            if count.isdigit():
                page_total += int(count)
                formatted_count = f"{int(count):,}"
            else:
                formatted_count = count
            
            counter += 1
            check_mark = "✅" if checked else "❌"
            embed.add_field(
                name=f"{counter}. {name}",
                value=f"{check_mark} {formatted_count}個",
                inline=True
            )
        
        # このページの合計
        embed.add_field(
            name=f"このページの合計",
            value=f"**{page_total:,}個**のアイテム",
            inline=False
        )
        
        # 全体の合計
        total_sum = sum(int(count) for _, count, _ in self.items if count.isdigit())
        embed.add_field(
            name="総合計",
            value=f"**{total_sum:,}個**のアイテム",
            inline=False
        )
        
        embed.set_footer(text=f"ShirafukasBOT • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        embed.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
        
        return embed


# 設計図削除確認用のViewクラス
class DeleteConfirmView(discord.ui.View):
    def __init__(self, list_title, csv_file_path, user):
        super().__init__(timeout=60)  # 60秒のタイムアウト
        self.list_title = list_title
        self.csv_file_path = csv_file_path
        self.user = user
    
    @discord.ui.button(label="削除する", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 権限チェック
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("このボタンは使用できません。", ephemeral=True)
            return
        
        try:
            # ファイルを直接削除（バックアップなし）
            os.remove(self.csv_file_path)
            
            # 成功時のembedを作成
            embed = discord.Embed(
                title="✅ 設計図削除完了",
                description=f"設計図 `{self.list_title}` を削除しました。",
                color=0x00FF00  # 成功は緑色
            )
            embed.set_footer(text=f"ShirafukasBOT • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            
            # ボタンを無効化して表示
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 設計図削除失敗",
                description=f"削除処理中にエラーが発生しました: `{str(e)}`",
                color=0xFF0000  # エラーは赤色
            )
            embed.set_footer(text="ShirafukasBOT")
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            
            await interaction.response.edit_message(embed=embed)
    
    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 権限チェック
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("このボタンは使用できません。", ephemeral=True)
            return
        
        # キャンセル時のembedを作成
        embed = discord.Embed(
            title="ℹ️ 削除キャンセル",
            description=f"設計図 `{self.list_title}` の削除をキャンセルしました。",
            color=0x808080  # キャンセルは灰色
        )
        embed.set_footer(text=f"ShirafukasBOT • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        
        # ボタンを無効化して表示
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)


def setup(bot: commands.Bot):
    @bot.tree.command(name="litematica-add", description="litematicaの材料ファイルを追加します")
    async def litematica_add(interaction: discord.Interaction, matica_title: str, file: discord.Attachment):
        await interaction.response.defer()
        
        # 処理開始を示すembedを作成
        embed = discord.Embed(
            title="litematicaファイル処理中",
            description="ファイルをアップロード中です...",
            color=0xFFFF00  # 処理中は黄色
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        processing_msg = await interaction.followup.send(embed=embed)
        
        try:
            # ディレクトリが存在しない場合は作成
            blueprint_dir = os.path.join(os.path.dirname(__file__), "blueprint")
            os.makedirs(blueprint_dir, exist_ok=True)
            
            # 元のファイルを保存（一時ファイルとして）
            temp_file_path = os.path.join(blueprint_dir, file.filename)
            await file.save(temp_file_path)
            
            csv_file_name = f"{matica_title}.csv"
            csv_file_path = os.path.join(blueprint_dir, csv_file_name)
            
            # 成功時のembedを更新
            embed = discord.Embed(
                title="✅ litematicaファイル追加成功",
                description=f"`{file.filename}`を追加しました\nCSV形式に変換しています...",
                color=0x00FF00  # 成功は緑色
            )

            # 複数のエンコーディングを試す
            encodings_to_try = ['utf-8', 'shift_jis', 'cp932', 'latin1']
            lines = None
            
            embed.add_field(name="タイトル", value=f"{matica_title}", inline=False)

            for encoding in encodings_to_try:
                try:
                    with open(temp_file_path, encoding=encoding) as f:
                        lines = f.readlines()
                        embed.add_field(name="エンコーディング", value=f"`{encoding}`で正常に読み込みました", inline=False)
                        break
                except UnicodeDecodeError:
                    continue
            
            # 読み込みに失敗した場合
            if lines is None:
                raise UnicodeDecodeError("すべてのエンコーディングで読み込みに失敗しました")
            
            litematica_data = []
            header_pattern = re.compile(r'\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|')
            row_pattern = re.compile(r'\|\s*(.*?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|')

            for line in lines:
                # ヘッダー行を検出
                if 'Item' in line and 'Total' in line:
                    headers = header_pattern.match(line)
                    if headers:
                        # ヘッダーに "check" 列を追加
                        columns = [headers.group(1), headers.group(2), "check"]
                        litematica_data.append(columns)
                # データ行取得
                else:
                    match = row_pattern.match(line)
                    if match:
                        # データ行にデフォルト値 "0" のcheck列を追加
                        row = [match.group(1), match.group(2), "0"]
                        litematica_data.append(row)
            
            # CSVとして保存（UTF-8で）
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(litematica_data)
            
            # Total列の合計値を計算
            total_sum = 0
            for row in litematica_data:
                # ヘッダー行をスキップ
                if row[0] == "Item" or "Item" in row[0]:
                    continue
                try:
                    # 2番目の要素がTotal値
                    if len(row) > 1 and row[1].isdigit():
                        total_sum += int(row[1])
                except (ValueError, IndexError):
                    # 数値変換できない場合や配列のインデックスが存在しない場合はスキップ
                    continue
            
            os.remove(temp_file_path)  # コメントアウトすると元のファイルも保持します
            
            embed.add_field(name="処理結果", value="ファイルの解析とCSV変換が完了しました", inline=False)
            embed.add_field(name="元ファイル", value=f"`{file.filename}`", inline=False)
            embed.add_field(name="保存名", value=f"`{csv_file_name}`", inline=True)
            embed.add_field(name="総アイテム数", value=f"{len(litematica_data) - 1} 種類", inline=True)
            embed.add_field(name="総アイテム個数", value=f"{total_sum:,} 個", inline=True)
            embed.set_footer(text=f"ShirafukasBOT • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            await processing_msg.edit(embed=embed)
            
        except Exception as e:
            # エラー時のembedを更新
            embed = discord.Embed(
                title="❌ litematicaファイル追加失敗",
                description=f"ファイルの処理中にエラーが発生しました: `{str(e)}`",
                color=0xFF0000  # エラーは赤色
            )
            embed.set_footer(text="ShirafukasBOT")
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            
            await processing_msg.edit(embed=embed)
    
    @bot.tree.command(name="litematica-list", description="litematicaの材料ファイルを一覧表示します")
    @app_commands.autocomplete(list_title=autocomplete_litematica_list)
    @app_commands.autocomplete(check=autocomplete_list_check)
    async def litematica_list(interaction: discord.Interaction, list_title: str, check: str):
        await interaction.response.defer()
        
        # 処理開始を示すembedを作成
        embed = discord.Embed(
            title=f"設計図の取得中: {list_title}",
            description="CSVファイルを読み込んでいます...",
            color=0xFFFF00  # 処理中は黄色
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        processing_msg = await interaction.followup.send(embed=embed)
        
        try:
            # CSVファイルのパス
            blueprint_dir = os.path.join(os.path.dirname(__file__), "blueprint")
            csv_file_path = os.path.join(blueprint_dir, f"{list_title}.csv")
            
            if not os.path.exists(csv_file_path):
                raise FileNotFoundError(f"ファイル {list_title}.csv が見つかりません。")
            
            # CSVファイルを読み込む
            items = []
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)  # ヘッダー行をスキップ
                
                for row in reader:
                    if len(row) >= 3:  # Item, Total, check の3つの列があるか確認
                        item_name = row[0]
                        total = row[1] if len(row[1]) > 0 else "0"
                        
                        # check列の値を確認 (0=未完了、1=完了)
                        check_value = row[2].strip() if len(row) > 2 else "0"
                        checked = check_value == "1"  # "1"の場合のみ完了とみなす
                        
                        # checkパラメータに応じたフィルタリング
                        if check == "all" or (check == "finished" and checked) or (check == "unfinished" and not checked):
                            items.append((item_name, total, checked))
            
            if len(items) > 0:
                # アイテム数でソート（多い順）
                items.sort(key=lambda x: int(x[1]) if x[1].isdigit() else 0, reverse=True)
                
                # ページネーションViewを作成
                view = ItemPaginationView(items, check, list_title, interaction.user)
                embed = view.create_embed()
                await processing_msg.edit(embed=embed, view=view)
            else:
                # アイテムがない場合
                status_text = "完了済み" if check == "finished" else ("未完了" if check == "unfinished" else "該当する")
                embed = discord.Embed(
                    title=f"{list_title} - {status_text}アイテム一覧",
                    description=f"**0個**のアイテムが{status_text}状態です。",
                    color=0x00FF00 if check == "finished" else (0x0000FF if check == "unfinished" else 0x9932CC)
                )
                embed.add_field(
                    name="アイテムなし",
                    value=f"{status_text}のアイテムはありません",
                    inline=True
                )
                embed.set_footer(text=f"ShirafukasBOT • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
                embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
                
                await processing_msg.edit(embed=embed)
            
        except Exception as e:
            # エラー時のembedを更新
            embed = discord.Embed(
                title="❌ リスト表示失敗",
                description=f"ファイルの処理中にエラーが発生しました: `{str(e)}`",
                color=0xFF0000  # エラーは赤色
            )
            embed.set_footer(text="ShirafukasBOT")
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            
            await processing_msg.edit(embed=embed)
    
    @bot.tree.command(name="litematica-check", description="litematicaの素材のチェック状態を変更します")
    @app_commands.autocomplete(list_title=autocomplete_litematica_list)
    @app_commands.autocomplete(item_name=autocomplete_item_name)
    @app_commands.autocomplete(check_status=autocomplete_check_status)
    async def litematica_check(
        interaction: discord.Interaction, 
        list_title: str, 
        item_name: str, 
        check_status: str
    ):
        await interaction.response.defer()
        
        # 処理開始を示すembedを作成
        embed = discord.Embed(
            title=f"チェック状態更新中: {list_title}",
            description="CSVファイルを編集しています...",
            color=0xFFFF00  # 処理中は黄色
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        processing_msg = await interaction.followup.send(embed=embed)
        
        try:
            # CSVファイルのパス
            blueprint_dir = os.path.join(os.path.dirname(__file__), "blueprint")
            csv_file_path = os.path.join(blueprint_dir, f"{list_title}.csv")
            
            if not os.path.exists(csv_file_path):
                raise FileNotFoundError(f"ファイル {list_title}.csv が見つかりません。")
            
            # CSVファイルを読み込み、編集する
            rows = []
            item_found = False
            item_index = -1
            original_check_value = ""
            
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)  # すべての行を一度にリストに読み込む
                
                # ヘッダー行を確認（0行目）
                if len(rows) > 0 and len(rows[0]) >= 3:
                    if rows[0][0] != "Item" or rows[0][2] != "check":
                        # 必要に応じてヘッダーを修正
                        rows[0] = ["Item", "Total", "check"]
                
                # アイテムを検索して状態を更新
                for i, row in enumerate(rows):
                    if i == 0:  # ヘッダー行はスキップ
                        continue
                        
                    if len(row) >= 1 and row[0] == item_name:
                        item_found = True
                        item_index = i
                        
                        # check列があるか確認
                        if len(row) >= 3:
                            original_check_value = row[2]
                            # 状態を更新
                            if check_status == "done":
                                row[2] = "1"
                            else:  # undone
                                row[2] = "0"
                        else:
                            # check列がない場合は追加
                            while len(row) < 3:
                                row.append("")
                            original_check_value = row[2]
                            if check_status == "done":
                                row[2] = "1"
                            else:  # undone
                                row[2] = "0"
                                
                        rows[i] = row
                        break
            
            if not item_found:
                raise ValueError(f"アイテム '{item_name}' が {list_title}.csv 内に見つかりませんでした。")
            
            # 更新したCSVを保存
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            
            # 成功時のembedを作成
            status_text = "完了" if check_status == "done" else "未完了"
            previous_status = "完了" if original_check_value == "1" else "未完了"
            
            embed = discord.Embed(
                title=f"✅ チェック状態更新成功",
                description=f"`{list_title}` の `{item_name}` のチェック状態を変更しました",
                color=0x00FF00  # 成功は緑色
            )
            
            embed.add_field(name="アイテム名", value=f"`{item_name}`", inline=True)
            embed.add_field(name="変更前", value=f"{previous_status} ({original_check_value})", inline=True)
            embed.add_field(name="変更後", value=f"{status_text} ({rows[item_index][2]})", inline=True)
            
            # アイテムの個数も表示
            if len(rows[item_index]) >= 2 and rows[item_index][1].isdigit():
                total = int(rows[item_index][1])
                embed.add_field(name="必要個数", value=f"{total:,} 個", inline=False)
            
            embed.set_footer(text=f"ShirafukasBOT • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            
            await processing_msg.edit(embed=embed)
            
        except Exception as e:
            # エラー時のembedを更新
            embed = discord.Embed(
                title="❌ チェック状態更新失敗",
                description=f"処理中にエラーが発生しました: `{str(e)}`",
                color=0xFF0000  # エラーは赤色
            )
            embed.set_footer(text="ShirafukasBOT")
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            
            await processing_msg.edit(embed=embed)
    
    @bot.tree.command(name="litematica-delete", description="litematicaの設計図を削除します")
    @app_commands.autocomplete(list_title=autocomplete_litematica_list)
    async def litematica_delete(interaction: discord.Interaction, list_title: str):
        await interaction.response.defer()
        
        # 処理開始を示すembedを作成
        embed = discord.Embed(
            title=f"設計図削除の確認: {list_title}",
            description="削除の確認を行います...",
            color=0xFFFF00  # 処理中は黄色
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        processing_msg = await interaction.followup.send(embed=embed)
        
        try:
            # CSVファイルのパス
            blueprint_dir = os.path.join(os.path.dirname(__file__), "blueprint")
            csv_file_path = os.path.join(blueprint_dir, f"{list_title}.csv")
            
            if not os.path.exists(csv_file_path):
                raise FileNotFoundError(f"ファイル {list_title}.csv が見つかりません。")
            
            # ファイル情報を取得
            file_size = os.path.getsize(csv_file_path)
            creation_time = os.path.getctime(csv_file_path)
            modified_time = os.path.getmtime(csv_file_path)
            
            # アイテム数を取得
            item_count = 0
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # ヘッダーをスキップ
                for _ in reader:
                    item_count += 1
            
            # 確認用のembedを作成
            embed = discord.Embed(
                title=f"⚠️ 設計図削除の確認: {list_title}",
                description=f"設計図 `{list_title}` を削除しますか？\n**この操作は取り消せません**（バックアップは自動作成されます）",
                color=0xFF9900  # 警告は橙色
            )
            
            # ファイル情報を表示
            embed.add_field(name="ファイル名", value=f"`{os.path.basename(csv_file_path)}`", inline=True)
            embed.add_field(name="ファイルサイズ", value=f"{file_size / 1024:.2f} KB", inline=True)
            embed.add_field(name="アイテム数", value=f"{item_count} 種類", inline=True)
            
            embed.add_field(
                name="作成日時", 
                value=f"{datetime.datetime.fromtimestamp(creation_time).strftime('%Y-%m-%d %H:%M:%S')}", 
                inline=True
            )
            embed.add_field(
                name="更新日時", 
                value=f"{datetime.datetime.fromtimestamp(modified_time).strftime('%Y-%m-%d %H:%M:%S')}", 
                inline=True
            )
            
            embed.set_footer(text=f"ShirafukasBOT • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            
            # 削除確認用ボタン付きで送信
            view = DeleteConfirmView(list_title, csv_file_path, interaction.user)
            await processing_msg.edit(embed=embed, view=view)
            
        except Exception as e:
            # エラー時のembedを更新
            embed = discord.Embed(
                title="❌ 設計図削除失敗",
                description=f"処理中にエラーが発生しました: `{str(e)}`",
                color=0xFF0000  # エラーは赤色
            )
            embed.set_footer(text="ShirafukasBOT")
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            
            await processing_msg.edit(embed=embed)