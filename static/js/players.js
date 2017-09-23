$(function() {
	fillSelect("/countries", "span.countryselect", "Code", "Id", function() {
		$(".countryselect").change(function() {
			updatePlayer();
			$(this).parent().next(".flag").html($(this).data("selectData")["Flag_Image"]);
		});
	});
	$(".playerfield").change(updatePlayer).keyup(updatePlayer);
	$(".addplayerbutton").click(addNewPlayer);
});
